"""Ops reserve ledger — ADR-008 / RFC-001.

Del semilla de USD 1.000 se reservan USD 150-250 para gastos operativos (VPS,
datos de mercado, LLM). Ese dinero no es P&L de trading: se contabiliza aparte
para que el capital tradable real (~750-850) y el kill switch -25% queden
limpios.

Diseño:
- Todo importe monetario es ``Decimal`` cuantizado a centavos (regla de
  integridad financiera del repo). Se rechaza ``float`` explícitamente.
- El almacenamiento está detrás de ``OpsLedgerStore`` para poder migrar a
  Postgres sin cambiar la API del ledger. La implementación por defecto es un
  JSON versionable en el repo.
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

DEFAULT_OPS_RESERVE_USD = Decimal("200")
DEFAULT_OPS_MONTHLY_CAP_USD = Decimal("50")
DEFAULT_OPS_LEDGER_PATH = "data/ops_ledger.json"

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
    ) -> None:
        self._store = store
        self._reserve_usd = to_money(reserve_usd)
        self._monthly_cap_usd = to_money(monthly_cap_usd)
        if self._reserve_usd < 0:
            raise OpsLedgerError(
                f"OPS_RESERVE_USD no puede ser negativo: {self._reserve_usd}"
            )
        if self._monthly_cap_usd < 0:
            raise OpsLedgerError(
                f"OPS_MONTHLY_CAP_USD no puede ser negativo: {self._monthly_cap_usd}"
            )

    @property
    def reserve_usd(self) -> Decimal:
        return self._reserve_usd

    @property
    def monthly_cap_usd(self) -> Decimal:
        return self._monthly_cap_usd

    def add_entry(
        self,
        *,
        date: DateLike,
        category: str,
        amount_usd: MoneyLike,
        note: str = "",
    ) -> OpsLedgerEntry:
        """Valida y persiste un gasto. Falla cerrado: si valida mal, no escribe."""
        entry = OpsLedgerEntry.create(
            date=date, category=category, amount_usd=amount_usd, note=note
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

        burn_total = sum((e.amount_usd for e in entries), Decimal("0"))
        burn_mtd = sum(
            (e.amount_usd for e in entries if e.month == current_month), Decimal("0")
        )
        months_observed = self._months_observed(entries, reference)
        projected_annual = self._project_annual(burn_total, months_observed)

        return {
            "ops_reserve_usd": self._reserve_usd,
            "ops_burn_mtd": burn_mtd.quantize(_CENTS, rounding=ROUND_HALF_UP),
            "ops_burn_total": burn_total.quantize(_CENTS, rounding=ROUND_HALF_UP),
            "ops_reserve_remaining": (self._reserve_usd - burn_total).quantize(
                _CENTS, rounding=ROUND_HALF_UP
            ),
            "monthly_cap": self._monthly_cap_usd,
            "cap_exceeded": burn_mtd > self._monthly_cap_usd,
            "projected_annual_burn": projected_annual,
            "reserve_exhausted_projection": projected_annual > self._reserve_usd,
            "month": current_month,
            "months_observed": months_observed,
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


def _env_money(name: str, default: Decimal) -> Decimal:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return to_money(default)
    try:
        return to_money(raw)
    except InvalidAmountError as exc:
        raise OpsLedgerError(f"{name} inválido: {raw!r} ({exc})") from exc


def get_ops_ledger_path() -> Path:
    return Path(os.getenv("OPS_LEDGER_PATH", DEFAULT_OPS_LEDGER_PATH))


def get_ops_ledger() -> OpsLedger:
    """Construye el ledger desde env en cada request (test-friendly, sin caché)."""
    return OpsLedger(
        store=JsonOpsLedgerStore(get_ops_ledger_path()),
        reserve_usd=_env_money("OPS_RESERVE_USD", DEFAULT_OPS_RESERVE_USD),
        monthly_cap_usd=_env_money("OPS_MONTHLY_CAP_USD", DEFAULT_OPS_MONTHLY_CAP_USD),
    )


def serialize_entry(entry: OpsLedgerEntry) -> Dict[str, Any]:
    return entry.to_row()


def serialize_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Serializa el summary para HTTP: dinero como string, nunca float."""
    return {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in summary.items()
    }
