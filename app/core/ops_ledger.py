"""Ops reserve ledger — ADR-008 / RFC-001, enmendado por CEO-01 (2026-08-05).

Los gastos operativos (VPS, datos, LLM) salen del mismo semilla de USD 1.000
que el capital de trading. La enmienda 01 del CEO recortó ops al mínimo durante
L0 porque la reserva prorrateada consumía 1,1-1,8% del capital tradable cada 21
días — del mismo orden que el PnL esperado del grid:

- Reserva objetivo <= USD 100 (antes 150-250).
- **Devengo mensual** de ~USD 15 en vez de comprometer 150-250 de golpe, para
  no destruir el colchón de riesgo el día uno.
- LLM pago excluido: su presupuesto en L0 es cero hasta que el Core demuestre
  PnL.

De ahí la distinción central del módulo:

- ``ops_reserve_total``: el techo de la reserva (<= 100). No se compromete.
- ``ops_reserve_committed``: lo devengado/gastado hasta hoy. **Este es el
  número que el risk engine resta al capital aportado** para obtener el capital
  tradable y el kill floor (CEO-01, Decisión 1), así que define cuánto puede
  perder el sistema antes de liquidar. Ver ``compute_tradable_capital``.

Diseño:
- Todo importe monetario es ``Decimal`` cuantizado a centavos (regla de
  integridad financiera del repo). Se rechaza ``float`` explícitamente.
- El devengo se calcula contra una fecha de referencia explícita, nunca contra
  ``datetime.now()`` implícito, para que el número que consume el risk engine
  sea reproducible y testeable.
- El almacenamiento está detrás de ``OpsLedgerStore`` para poder migrar a
  Postgres sin cambiar la API del ledger. La implementación por defecto es un
  JSON versionable (ADR-008 autoriza tabla **o** JSON). Sin migración Alembic
  en este slice: en Docker Compose el path va a un **volume nombrado**
  (``ops_ledger_data`` → ``/var/lib/gridbot/ops``) para que el gasto sobreviva
  recreate de contenedor; el FS efímero de dynos Heroku sigue siendo riesgo
  hasta Postgres P1 o disco persistente. Ver ``Docs/ops/ops-ledger-persistence.md``.
- Módulo sin efectos secundarios de trading: no abre órdenes ni lee flags de
  modo. Paper/live es irrelevante acá.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Union

OPS_CATEGORIES: tuple[str, ...] = ("vps", "data", "llm", "other")

# Post CEO-01 (Decisión 3): ops al mínimo durante L0.
DEFAULT_OPS_RESERVE_USD = Decimal("100")
DEFAULT_OPS_MONTHLY_CAP_USD = Decimal("10")  # CEO Acta 02: cap 10; pico mes malo 12 (policy)
# Fecha del All Hands que arrancó el programa: mes 0 del devengo.
DEFAULT_OPS_ACCRUAL_START = date_type(2026, 8, 5)
# LLM pago no consume presupuesto hasta que el Core demuestre PnL.
DEFAULT_OPS_EXCLUDED_CATEGORIES: tuple[str, ...] = ("llm",)
# Default no-Docker / repo checkout. Compose monta volume nombrado y overridea
# OPS_LEDGER_PATH a PERSISTENT_OPS_LEDGER_PATH (B19 / kill floor).
DEFAULT_OPS_LEDGER_PATH = "data/ops_ledger.json"
PERSISTENT_OPS_LEDGER_PATH = "/var/lib/gridbot/ops/ops_ledger.json"

LEDGER_SCHEMA_VERSION = 1
CURRENCY = "USD"

_CENTS = Decimal("0.01")
_MONTHS_PER_YEAR = Decimal("12")

DateLike = Union[str, date_type, datetime]
MoneyLike = Union[str, int, Decimal]


class OpsLedgerError(ValueError):
    """Error de dominio del ledger de ops."""


class InvalidCategoryError(OpsLedgerError):
    """Categoría fuera del set de ADR-008."""


class CategoryExcludedError(OpsLedgerError):
    """Categoría válida pero con presupuesto cero por política (L0: ``llm``).

    Deliberadamente **no** hereda de :class:`InvalidCategoryError`: la categoría
    existe y volverá a tener presupuesto cuando se levante la exclusión.
    """


class InvalidAmountError(OpsLedgerError):
    """Importe no positivo, no finito o de tipo inseguro (float)."""


class InvalidDateError(OpsLedgerError):
    """Fecha o mes con formato no ISO."""


class OpsLedgerStorageError(OpsLedgerError):
    """El store no pudo leer/escribir el ledger."""


def to_money(value: MoneyLike) -> Decimal:
    """Normaliza un importe a ``Decimal`` con 2 decimales (ROUND_HALF_UP).

    ``float`` se rechaza a propósito: la regla de integridad financiera del
    repo prohíbe binario flotante para dinero.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise InvalidAmountError(
            f"amount_usd debe ser Decimal, str o int (recibido {type(value).__name__}); "
            "float está prohibido por precisión financiera"
        )
    if isinstance(value, Decimal):
        raw = value
    elif isinstance(value, (int, str)):
        try:
            raw = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            raise InvalidAmountError(f"amount_usd no parseable: {value!r}") from exc
    else:
        raise InvalidAmountError(
            f"amount_usd de tipo no soportado: {type(value).__name__}"
        )

    if not raw.is_finite():
        raise InvalidAmountError(f"amount_usd debe ser finito: {value!r}")
    return raw.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _to_date(value: DateLike) -> date_type:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date_type):
        return value
    if isinstance(value, str):
        try:
            return date_type.fromisoformat(value.strip())
        except ValueError as exc:
            raise InvalidDateError(
                f"date debe ser ISO YYYY-MM-DD (recibido {value!r})"
            ) from exc
    raise InvalidDateError(f"date de tipo no soportado: {type(value).__name__}")


def _month_key(value: date_type) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _full_months_elapsed(start: date_type, reference: date_type) -> int:
    """Meses **completos** entre ``start`` y ``reference`` (nunca negativo).

    Con inicio el 5 de agosto, el 4 de septiembre devenga 0 y el 5 devenga 1: el
    mes se devenga cuando se cumple, no cuando arranca.
    """
    months = (reference.year - start.year) * 12 + (reference.month - start.month)
    if reference.day < start.day:
        months -= 1
    return max(0, months)


def _normalize_categories(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        raw = [part for part in value.split(",")]
    else:
        raw = list(value)
    categories = []
    for item in raw:
        name = str(item).strip().lower()
        if not name:
            continue
        if name not in OPS_CATEGORIES:
            raise InvalidCategoryError(
                f"category inválida: {name!r}; válidas: {', '.join(OPS_CATEGORIES)}"
            )
        if name not in categories:
            categories.append(name)
    return tuple(categories)


def _validate_month(month: str) -> str:
    if not isinstance(month, str):
        raise InvalidDateError(f"month de tipo no soportado: {type(month).__name__}")
    parts = month.strip().split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
        raise InvalidDateError(f"month debe ser ISO YYYY-MM (recibido {month!r})")
    try:
        year, mon = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise InvalidDateError(
            f"month debe ser ISO YYYY-MM (recibido {month!r})"
        ) from exc
    if not 1 <= mon <= 12:
        raise InvalidDateError(f"month fuera de rango: {month!r}")
    return f"{year:04d}-{mon:02d}"


@dataclass(frozen=True)
class OpsLedgerEntry:
    """Gasto operativo puntual imputado a la reserva de ops."""

    date: date_type
    category: str
    amount_usd: Decimal
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.date, date_type) or isinstance(self.date, datetime):
            raise InvalidDateError("date debe ser datetime.date")
        if self.category not in OPS_CATEGORIES:
            raise InvalidCategoryError(
                f"category inválida: {self.category!r}; válidas: {', '.join(OPS_CATEGORIES)}"
            )
        if not isinstance(self.amount_usd, Decimal):
            raise InvalidAmountError("amount_usd debe ser Decimal")
        if self.amount_usd <= 0:
            raise InvalidAmountError(
                f"amount_usd debe ser > 0 (recibido {self.amount_usd})"
            )

    @classmethod
    def create(
        cls,
        *,
        date: DateLike,
        category: str,
        amount_usd: MoneyLike,
        note: str = "",
    ) -> "OpsLedgerEntry":
        """Normaliza tipos y valida invariantes antes de construir la entrada."""
        return cls(
            date=_to_date(date),
            category=str(category).strip().lower(),
            amount_usd=to_money(amount_usd),
            note=(note or "").strip(),
        )

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "OpsLedgerEntry":
        try:
            return cls.create(
                date=row["date"],
                category=row["category"],
                amount_usd=row["amount_usd"],
                note=row.get("note", ""),
            )
        except KeyError as exc:
            raise OpsLedgerStorageError(
                f"Fila de ledger incompleta: falta {exc}"
            ) from exc

    @property
    def month(self) -> str:
        return _month_key(self.date)

    def to_row(self) -> Dict[str, Any]:
        """Representación serializable; dinero como string para no perder escala."""
        return {
            "date": self.date.isoformat(),
            "category": self.category,
            "amount_usd": str(self.amount_usd),
            "note": self.note,
        }


class OpsLedgerStore(Protocol):
    """Persistencia del ledger. Implementación Postgres futura: mismo contrato."""

    def read_all(self) -> List[Dict[str, Any]]: ...

    def write_all(self, rows: Sequence[Dict[str, Any]]) -> None: ...


class JsonOpsLedgerStore:
    """Store JSON de archivo único, escritura atómica.

    Formato: ``{"version": 1, "currency": "USD", "entries": [...]}``.
    Tolera una lista pelada para ledgers escritos a mano.
    """

    def __init__(self, path: Union[str, Path]) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def read_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError) as exc:
            raise OpsLedgerStorageError(
                f"Ledger ilegible en {self._path}: {exc}"
            ) from exc

        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = payload.get("entries", [])
        else:
            raise OpsLedgerStorageError(
                f"Ledger con formato inesperado en {self._path}"
            )

        if not isinstance(rows, list):
            raise OpsLedgerStorageError(f"'entries' debe ser lista en {self._path}")
        return [dict(row) for row in rows]

    def write_all(self, rows: Sequence[Dict[str, Any]]) -> None:
        payload = {
            "version": LEDGER_SCHEMA_VERSION,
            "currency": CURRENCY,
            "entries": list(rows),
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp_path, self._path)
        except OSError as exc:
            raise OpsLedgerStorageError(
                f"No se pudo escribir el ledger en {self._path}: {exc}"
            ) from exc


class OpsLedger:
    """Ledger de la reserva de ops con agregados para el dashboard del CEO."""

    def __init__(
        self,
        store: OpsLedgerStore,
        reserve_usd: MoneyLike = DEFAULT_OPS_RESERVE_USD,
        monthly_cap_usd: MoneyLike = DEFAULT_OPS_MONTHLY_CAP_USD,
        accrual_start: Optional[DateLike] = None,
        excluded_categories: Optional[Any] = None,
    ) -> None:
        self._store = store
        self._reserve_usd = to_money(reserve_usd)
        self._monthly_cap_usd = to_money(monthly_cap_usd)
        self._accrual_start = (
            _to_date(accrual_start)
            if accrual_start is not None
            else DEFAULT_OPS_ACCRUAL_START
        )
        self._excluded_categories = (
            _normalize_categories(excluded_categories)
            if excluded_categories is not None
            else DEFAULT_OPS_EXCLUDED_CATEGORIES
        )
        if self._reserve_usd < 0:
            raise OpsLedgerError(
                f"OPS_RESERVE_USD no puede ser negativo: {self._reserve_usd}"
            )
        if self._monthly_cap_usd < 0:
            raise OpsLedgerError(
                f"OPS_MONTHLY_CAP_USD no puede ser negativo: {self._monthly_cap_usd}"
            )

    @property
    def reserve_total_usd(self) -> Decimal:
        """Techo de la reserva. No es lo comprometido: ver ``committed_usd``."""
        return self._reserve_usd

    @property
    def monthly_cap_usd(self) -> Decimal:
        return self._monthly_cap_usd

    @property
    def monthly_accrual_usd(self) -> Decimal:
        """Devengo mensual. Mismo valor que el cap: se devenga lo presupuestado."""
        return self._monthly_cap_usd

    @property
    def accrual_start(self) -> date_type:
        return self._accrual_start

    @property
    def excluded_categories(self) -> tuple[str, ...]:
        return self._excluded_categories

    def category_budgets(self) -> Dict[str, Decimal]:
        """Presupuesto mensual por categoría; cero para las excluidas en L0."""
        return {
            category: (
                Decimal("0.00")
                if category in self._excluded_categories
                else self._monthly_cap_usd
            )
            for category in OPS_CATEGORIES
        }

    def accrued_to_date(
        self, now: Optional[Union[datetime, date_type]] = None
    ) -> Decimal:
        """Devengo acumulado a la fecha, topeado por ``reserve_total_usd``."""
        reference = _to_date(now) if now is not None else date_type.today()
        months = _full_months_elapsed(self._accrual_start, reference)
        accrued = self.monthly_accrual_usd * Decimal(months)
        return min(accrued, self._reserve_usd).quantize(
            _CENTS, rounding=ROUND_HALF_UP
        )

    def committed_usd(
        self, now: Optional[Union[datetime, date_type]] = None
    ) -> Decimal:
        """Reserva comprometida: contrato que consume el risk engine (Track A).

        Es el máximo entre el devengo y el gasto real. El devengo está topeado por
        el techo de la reserva, el gasto real no: si se gastó más de lo previsto,
        esa plata ya no está y el capital tradable tiene que reflejarlo, o el kill
        floor quedaría por debajo del capital que existe de verdad.
        """
        accrued = self.accrued_to_date(now)
        burn_total = self.burn_total()
        return max(accrued, burn_total)

    def burn_total(self) -> Decimal:
        entries = self.list_entries()
        total = sum((e.amount_usd for e in entries), Decimal("0"))
        return total.quantize(_CENTS, rounding=ROUND_HALF_UP)

    def tradable_capital(
        self,
        contributed_capital: MoneyLike,
        now: Optional[Union[datetime, date_type]] = None,
    ) -> Decimal:
        """``contributed_capital - ops_reserve_committed`` (CEO-01, Decisión 1)."""
        return compute_tradable_capital(contributed_capital, self.committed_usd(now))

    def add_entry(
        self,
        *,
        date: DateLike,
        category: str,
        amount_usd: MoneyLike,
        note: str = "",
        allow_excluded: bool = False,
    ) -> OpsLedgerEntry:
        """Valida y persiste un gasto. Falla cerrado: si valida mal, no escribe.

        Una categoría excluida se rechaza por defecto (en L0, ``llm``).
        ``allow_excluded=True`` es la salida de auditoría para cuando la plata se
        gastó igual: el ledger no debe mentir sobre el cash, y el summary marca
        la violación de política vía ``l0_policy_violation``.
        """
        entry = OpsLedgerEntry.create(
            date=date, category=category, amount_usd=amount_usd, note=note
        )
        if entry.category in self._excluded_categories and not allow_excluded:
            raise CategoryExcludedError(
                f"category {entry.category!r} tiene presupuesto cero en L0 "
                "(CEO-01, Decisión 3); usar allow_excluded=True solo para "
                "registrar un gasto ya ejecutado"
            )
        rows = self._store.read_all()
        rows.append(entry.to_row())
        self._store.write_all(rows)
        return entry

    def list_entries(self, month: Optional[str] = None) -> List[OpsLedgerEntry]:
        """Entradas ordenadas por fecha; ``month`` filtra por 'YYYY-MM'."""
        wanted = _validate_month(month) if month is not None else None
        entries = [OpsLedgerEntry.from_row(row) for row in self._store.read_all()]
        if wanted is not None:
            entries = [e for e in entries if e.month == wanted]
        return sorted(entries, key=lambda e: (e.date, e.category))

    def summary(
        self, now: Optional[Union[datetime, date_type]] = None
    ) -> Dict[str, Any]:
        """Agregados de burn y proyección. Dinero en ``Decimal`` de 2 decimales."""
        reference = _to_date(now) if now is not None else date_type.today()
        current_month = _month_key(reference)
        entries = self.list_entries()

        burn_total = sum((e.amount_usd for e in entries), Decimal("0")).quantize(
            _CENTS, rounding=ROUND_HALF_UP
        )
        burn_mtd = sum(
            (e.amount_usd for e in entries if e.month == current_month), Decimal("0")
        ).quantize(_CENTS, rounding=ROUND_HALF_UP)
        excluded_burn = sum(
            (
                e.amount_usd
                for e in entries
                if e.category in self._excluded_categories
            ),
            Decimal("0"),
        ).quantize(_CENTS, rounding=ROUND_HALF_UP)

        months_observed = self._months_observed(entries, reference)
        projected_annual = self._project_annual(burn_total, months_observed)

        accrual_months = _full_months_elapsed(self._accrual_start, reference)
        accrued = self.accrued_to_date(reference)
        committed = max(accrued, burn_total)

        return {
            # Reserva y devengo — CEO-01, Decisión 3
            "ops_reserve_total": self._reserve_usd,
            "ops_reserve_committed": committed,
            "ops_accrued_to_date": accrued,
            "ops_monthly_accrual": self.monthly_accrual_usd,
            "ops_accrual_start": self._accrual_start,
            "ops_accrual_months": accrual_months,
            "committed_driven_by_burn": burn_total > accrued,
            # Gasto real
            "ops_burn_mtd": burn_mtd,
            "ops_burn_total": burn_total,
            "ops_reserve_remaining": (self._reserve_usd - burn_total).quantize(
                _CENTS, rounding=ROUND_HALF_UP
            ),
            "monthly_cap": self._monthly_cap_usd,
            "cap_exceeded": burn_mtd > self._monthly_cap_usd,
            # Proyección — ADR-008 #4
            "projected_annual_burn": projected_annual,
            "reserve_exhausted_projection": projected_annual > self._reserve_usd,
            "months_observed": months_observed,
            # Política L0
            "excluded_categories": self._excluded_categories,
            "excluded_category_burn": excluded_burn,
            "category_budgets": self.category_budgets(),
            "l0_policy_violation": excluded_burn > 0,
            # Meta
            "month": current_month,
            "entries_count": len(entries),
            "currency": CURRENCY,
        }

    @staticmethod
    def _months_observed(
        entries: Sequence[OpsLedgerEntry], reference: date_type
    ) -> int:
        """Meses calendario desde el primer gasto hasta ``reference``, inclusive.

        Cuenta los huecos: un único gasto en junio con referencia en agosto son
        3 meses, no 1. Así el run-rate no se infla por meses sin gasto.
        """
        if not entries:
            return 0
        first = min(e.date for e in entries)
        elapsed = (reference.year - first.year) * 12 + (reference.month - first.month)
        return max(1, elapsed + 1)

    @staticmethod
    def _project_annual(burn_total: Decimal, months_observed: int) -> Decimal:
        """Anualiza el promedio mensual observado (ADR-008 #4: alerta de burn).

        Conservador por diseño: el mes en curso cuenta completo, así que un mes
        parcial caro dispara la alerta antes en vez de después.
        """
        if months_observed <= 0 or burn_total == 0:
            return Decimal("0.00")
        avg_monthly = burn_total / Decimal(months_observed)
        return (avg_monthly * _MONTHS_PER_YEAR).quantize(
            _CENTS, rounding=ROUND_HALF_UP
        )


def compute_tradable_capital(
    contributed_capital: MoneyLike, ops_reserve_committed: MoneyLike
) -> Decimal:
    """Capital tradable = aportado − reserva de ops comprometida.

    Contrato único para el risk engine (CEO-01, Decisión 1): de acá sale el
    ``kill_floor = tradable_capital * 0.75``. Vive en este módulo para que el
    ledger y el motor de riesgo no puedan derivar dos números distintos.
    """
    return (to_money(contributed_capital) - to_money(ops_reserve_committed)).quantize(
        _CENTS, rounding=ROUND_HALF_UP
    )


def _env_money(name: str, default: Decimal) -> Decimal:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return to_money(default)
    try:
        return to_money(raw)
    except InvalidAmountError as exc:
        raise OpsLedgerError(f"{name} inválido: {raw!r} ({exc})") from exc


def _env_date(name: str, default: date_type) -> date_type:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return _to_date(raw)
    except InvalidDateError as exc:
        raise OpsLedgerError(f"{name} inválido: {raw!r} ({exc})") from exc


def _env_categories(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return _normalize_categories(raw)
    except InvalidCategoryError as exc:
        raise OpsLedgerError(f"{name} inválido: {raw!r} ({exc})") from exc


def get_ops_ledger_path() -> Path:
    return Path(os.getenv("OPS_LEDGER_PATH", DEFAULT_OPS_LEDGER_PATH))


def get_ops_ledger() -> OpsLedger:
    """Construye el ledger desde env en cada request (test-friendly, sin caché)."""
    return OpsLedger(
        store=JsonOpsLedgerStore(get_ops_ledger_path()),
        reserve_usd=_env_money("OPS_RESERVE_USD", DEFAULT_OPS_RESERVE_USD),
        monthly_cap_usd=_env_money("OPS_MONTHLY_CAP_USD", DEFAULT_OPS_MONTHLY_CAP_USD),
        accrual_start=_env_date("OPS_ACCRUAL_START", DEFAULT_OPS_ACCRUAL_START),
        excluded_categories=_env_categories(
            "OPS_EXCLUDED_CATEGORIES", DEFAULT_OPS_EXCLUDED_CATEGORIES
        ),
    )


def serialize_entry(entry: OpsLedgerEntry) -> Dict[str, Any]:
    return entry.to_row()


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date_type):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def serialize_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Serializa el summary para HTTP: dinero como string, nunca float."""
    return {key: _serialize_value(value) for key, value in summary.items()}


def get_ops_summary() -> Dict[str, Any]:
    """Facade para el adaptador CEO (`app.core.ceo_overview` / ADR-005)."""
    from datetime import datetime, timezone

    summary = get_ops_ledger().summary()
    # B20: refresca gauges / Telegram cuando el CEO overview consulta ops.
    try:
        from app.core.ops_cap_alerts import emit_ops_cap_alerts

        emit_ops_cap_alerts(summary)
    except Exception:
        pass
    payload = serialize_summary(summary)
    payload.setdefault("as_of", datetime.now(timezone.utc).isoformat())
    return payload
