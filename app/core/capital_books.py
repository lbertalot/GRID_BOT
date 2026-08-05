"""Unified capital ledger — minimal multi-book view (P0 slice S6, ADR-004 / RFC-003).

Un solo pool de capital contable, tres books lógicos:

    core_grid       70%  · engine GRID_BOT        · único book con live habilitado en L0
    sat_systematic  20%  · engine freqtrade       · paper/dry-run en L0
    sat_signals     10%  · engine TradingAgents   · paper en L0

## Dos capitales, no uno (CEO Amendment 01, 2026-08-05)

Ops se devenga **mensualmente** (~USD 10–15/mes) contra un **techo** de USD 100, en vez
de comprometerse de golpe. Eso parte el número en dos, y confundirlos es un error caro:

- `tradable_capital` = `contributed − ops_reserve_committed`. Es el capital real de hoy
  y **la base del kill** (Decisión 1 de la enmienda). Sube a medida que queda claro que
  no gastamos: al go-live 2026-09-15 se espera ~970–985, no 900.
- `tradable_capital_floor` = `contributed − ops_reserve_cap` (1000 − 100 = 900). Es el
  peor caso bajo la política de ops, y **la base de los notional caps**.

Los `notional_cap_usd` se fijan sobre el **piso** a propósito: si se derivaran del
tradable real, el sizing de cada book se movería cada mes con el devengo de ops —
el desk operaría con caps distintos en septiembre y en octubre sin que haya cambiado
ninguna decisión de trading. Con el piso, los caps son estables y siempre financiables;
el capital que sobra por no haber gastado ops queda como colchón, no como más riesgo.
El `consolidated_equity` sí usa el committed real, porque el kill mide plata de verdad.

## Quién es dueño de qué

`ops_reserve_committed` lo produce el **Track B** (`ops_ledger`), no este módulo. Se
resuelve en este orden: parámetro explícito → `app.core.ops_ledger` → env
`OPS_RESERVE_COMMITTED_USD` → `0.00`. El snapshot expone siempre
`ops_reserve_committed_source` para que el dashboard no muestre un default como si
fuera un dato del ledger. Si el ledger existe pero falla, la fuente es `unavailable`:
degradamos con un default conservador (committed 0 ⇒ tradable más alto ⇒ kill floor más
alto ⇒ dispara antes), nunca con un número viejo disfrazado de actual.

## Alcance L0 (AC-S6.5)

Esto es **allocations + caps + lectura**, no contabilidad completa. El PnL de los
satellites es ingest **manual/externo**: se escribe a mano en
`config/capital_books.json` (`books[].manual_pnl`) con el corte del tear sheet, o se
inyecta por `pnl_overrides`. El tagging de fills por book y los adapters de freqtrade
quedan para P1.

Fail-closed: cualquier config inválida levanta `CapitalBooksConfigError` en vez de
devolver números que parezcan válidos. Todo el dinero es `Decimal`; un `float` en un
campo monetario es un error, no una conversión silenciosa.

Este módulo no habilita trading real: `live_enabled` es una declaración de política y
en L0 sólo `core_grid` puede tenerla en `true`.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

CORE_BOOK_ID = "core_grid"
KNOWN_BOOK_IDS: Tuple[str, ...] = ("core_grid", "sat_systematic", "sat_signals")

# L0 (gate 2026-09-15): sólo el Core Grid opera con dinero real. Los satellites
# tienen asignación declarada pero corren en paper. Cambiar esto exige ADR + gate
# humano (`.cursor/rules/40-no-live-without-gate.mdc`), no una edición de config.
L0_LIVE_ALLOWED_BOOK_IDS = frozenset({CORE_BOOK_ID})

# Techo de la reserva de ops en L0 (CEO Amendment 01, Decisión 3). Antes era 150–250;
# subirlo de nuevo baja el capital tradable y encarece el hurdle de la estrategia, así
# que exige otra decisión del CEO, no una edición de JSON.
L0_OPS_RESERVE_CAP_USD = Decimal("100")

# Contrato esperado del Track B para el devengado de ops.
OPS_LEDGER_MODULE = "app.core.ops_ledger"
OPS_LEDGER_GETTER = "get_ops_reserve_committed_usd"

VALID_PNL_SOURCES = frozenset({"internal", "manual"})
_PNL_FIELDS = ("realized_pnl", "unrealized_pnl")

NOTIONAL_CAP_POLICY = "fixed_on_tradable_floor"

PNL_NOTE = (
    "PnL de satellites es carga manual en L0: se edita en config/capital_books.json "
    "(books[].manual_pnl) o se inyecta vía pnl_overrides. Sólo core_grid reporta PnL "
    "interno del engine."
)

CAPITAL_NOTE = (
    "Los notional caps se fijan sobre tradable_capital_floor (aportado − techo de ops) "
    "para que el sizing no se mueva con el devengo mensual de ops. El kill y el equity "
    "consolidado usan tradable_capital (aportado − ops devengado), que es plata real."
)

_CENTS = Decimal("0.01")
_HUNDRED = Decimal("100")
_ZERO = Decimal("0.00")

_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "capital_books.json"
)


class CapitalBooksConfigError(ValueError):
    """Config de books inválida o inconsistente. Siempre trae el motivo."""


@dataclass(frozen=True)
class BookAllocation:
    book_id: str
    engine: str
    allocation_pct: Decimal
    live_enabled: bool
    pnl_source: str
    realized_pnl: Decimal
    unrealized_pnl: Decimal


@dataclass(frozen=True)
class CapitalBooksConfig:
    """Política estática de capital. El devengado de ops **no** vive acá: es estado
    del Track B y se resuelve por snapshot."""

    version: int
    contributed_capital_usd: Decimal
    ops_reserve_cap_usd: Decimal
    tradable_capital_floor_usd: Decimal
    books: Tuple[BookAllocation, ...]


def _to_decimal(value: Any, field: str) -> Decimal:
    """Convierte a Decimal rechazando float (regla `10-financial-integrity`)."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (bool, float)):
        raise CapitalBooksConfigError(
            f"{field}: tipo no permitido en montos ({value!r}); "
            "usar str o Decimal, nunca float"
        )
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str) and value.strip():
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            raise CapitalBooksConfigError(f"{field}: valor no numérico ({value!r})")
    raise CapitalBooksConfigError(f"{field}: valor no numérico ({value!r})")


def _money(value: Decimal, rounding: str = ROUND_HALF_EVEN) -> Decimal:
    return value.quantize(_CENTS, rounding=rounding)


def _parse_pnl(raw: Mapping[str, Any], field_prefix: str) -> Tuple[Decimal, Decimal]:
    realized = _to_decimal(raw.get("realized_pnl", "0"), f"{field_prefix}.realized_pnl")
    unrealized = _to_decimal(
        raw.get("unrealized_pnl", "0"), f"{field_prefix}.unrealized_pnl"
    )
    return _money(realized), _money(unrealized)


def _resolve_tradable_floor(
    contributed: Decimal, ops_reserve_cap: Decimal, override_raw: Optional[str]
) -> Decimal:
    """Piso de capital tradable = aportado − techo de ops, salvo override explícito.

    El override sólo puede bajar el piso: nunca puede comerse la reserva de ops
    (AC-S5.1), porque la reserva no es capital dimensionable.
    """
    derived = contributed - ops_reserve_cap
    if derived <= 0:
        raise CapitalBooksConfigError(
            f"piso de capital tradable no positivo: contributed={contributed} "
            f"− ops_reserve_cap={ops_reserve_cap} = {derived}"
        )
    if override_raw is None:
        return _money(derived)

    try:
        override = _to_decimal(override_raw, "TRADABLE_CAPITAL_USD")
    except CapitalBooksConfigError as exc:
        raise CapitalBooksConfigError(f"TRADABLE_CAPITAL_USD inválido: {exc}")
    if override <= 0:
        raise CapitalBooksConfigError(
            f"TRADABLE_CAPITAL_USD debe ser > 0 (recibido {override})"
        )
    if override > derived:
        raise CapitalBooksConfigError(
            f"TRADABLE_CAPITAL_USD={override} excede el piso tradable {derived} "
            f"(contributed {contributed} − ops_reserve_cap {ops_reserve_cap}); "
            "la reserva de ops no es capital tradable"
        )
    return _money(override)


def _committed_from_ops_ledger() -> Tuple[Optional[Decimal], bool]:
    """Lee el devengado del Track B. Devuelve `(valor, ledger_roto)`.

    Contrato esperado: `app.core.ops_ledger.get_ops_reserve_committed_usd() -> Decimal`
    con el ops devengado acumulado en USD (≥ 0, sin float). Si el módulo no existe
    todavía, no es un error: seguimos con env/default.
    """
    try:
        module = importlib.import_module(OPS_LEDGER_MODULE)
    except ImportError:
        return None, False

    getter = getattr(module, OPS_LEDGER_GETTER, None)
    if getter is None:
        logger.warning(
            "%s existe pero no expone %s(); se usa env/default para el ops devengado",
            OPS_LEDGER_MODULE,
            OPS_LEDGER_GETTER,
        )
        return None, True
    try:
        value = _to_decimal(getter(), f"{OPS_LEDGER_MODULE}.{OPS_LEDGER_GETTER}()")
    except Exception as exc:
        # Un bug del Track B no puede romper la lectura de books ni inventar un
        # número: degradamos a `unavailable` y que el dashboard lo muestre.
        logger.warning("ops ledger no disponible para el devengado de ops: %s", exc)
        return None, True
    return value, False


def _resolve_ops_reserve_committed(
    contributed: Decimal, explicit: Optional[Any]
) -> Tuple[Decimal, str]:
    """Devengado de ops + su fuente. Orden: explícito → ops_ledger → env → default."""
    if explicit is not None:
        committed, source = _to_decimal(explicit, "ops_reserve_committed"), "explicit"
    else:
        ledger_value, ledger_broken = _committed_from_ops_ledger()
        env_raw = os.getenv("OPS_RESERVE_COMMITTED_USD")
        if ledger_value is not None:
            committed, source = ledger_value, "ops_ledger"
        elif env_raw is not None:
            try:
                committed = _to_decimal(env_raw, "OPS_RESERVE_COMMITTED_USD")
            except CapitalBooksConfigError as exc:
                raise CapitalBooksConfigError(
                    f"OPS_RESERVE_COMMITTED_USD inválido: {exc}"
                )
            source = "env"
        elif ledger_broken:
            committed, source = _ZERO, "unavailable"
        else:
            committed, source = _ZERO, "default"

    if committed < 0:
        raise CapitalBooksConfigError(
            f"ops_reserve_committed no puede ser negativo (recibido {committed})"
        )
    if committed >= contributed:
        raise CapitalBooksConfigError(
            f"ops_reserve_committed={committed} deja el capital tradable en cero o "
            f"negativo frente al aportado {contributed}"
        )
    return _money(committed), source


def _validate_book_ids(book_ids: Iterable[str]) -> None:
    seen: set[str] = set()
    for book_id in book_ids:
        if book_id in seen:
            raise CapitalBooksConfigError(f"book_id duplicado en la config: {book_id}")
        if book_id not in KNOWN_BOOK_IDS:
            raise CapitalBooksConfigError(
                f"book_id desconocido: {book_id}; permitidos {list(KNOWN_BOOK_IDS)}"
            )
        seen.add(book_id)
    missing = [book_id for book_id in KNOWN_BOOK_IDS if book_id not in seen]
    if missing:
        raise CapitalBooksConfigError(
            f"faltan books en la config: {missing}; se esperan {list(KNOWN_BOOK_IDS)}"
        )


def parse_capital_books_config(
    raw: Mapping[str, Any], *, tradable_capital_override: Optional[str] = None
) -> CapitalBooksConfig:
    """Valida la config cruda (JSON versionado) y devuelve la política tipada."""
    if not isinstance(raw, Mapping):
        raise CapitalBooksConfigError("la config de books debe ser un objeto JSON")

    raw_books = raw.get("books")
    if not isinstance(raw_books, list) or not raw_books:
        raise CapitalBooksConfigError("la config no declara books")

    contributed = _to_decimal(
        raw.get("contributed_capital_usd", "0"), "contributed_capital_usd"
    )
    ops_reserve_cap = _to_decimal(
        raw.get("ops_reserve_cap_usd", "0"), "ops_reserve_cap_usd"
    )
    if contributed <= 0:
        raise CapitalBooksConfigError(
            f"contributed_capital_usd debe ser > 0 (recibido {contributed})"
        )
    if ops_reserve_cap < 0:
        raise CapitalBooksConfigError(
            f"ops_reserve_cap_usd no puede ser negativo (recibido {ops_reserve_cap})"
        )
    if ops_reserve_cap > L0_OPS_RESERVE_CAP_USD:
        raise CapitalBooksConfigError(
            f"ops_reserve_cap_usd={ops_reserve_cap} supera el techo de ops de L0 "
            f"({L0_OPS_RESERVE_CAP_USD}) fijado en CEO Amendment 01; subirlo exige "
            "una decisión del CEO, no una edición de config"
        )

    tradable_floor = _resolve_tradable_floor(
        contributed, ops_reserve_cap, tradable_capital_override
    )

    _validate_book_ids(entry.get("book_id") for entry in raw_books)

    books = []
    total_pct = Decimal("0")
    for entry in raw_books:
        book_id = entry["book_id"]
        pct = _to_decimal(entry.get("allocation_pct"), f"{book_id}.allocation_pct")
        if pct < 0:
            raise CapitalBooksConfigError(
                f"{book_id}.allocation_pct no puede ser negativo (recibido {pct})"
            )
        total_pct += pct

        live_enabled = bool(entry.get("live_enabled", False))
        if live_enabled and book_id not in L0_LIVE_ALLOWED_BOOK_IDS:
            raise CapitalBooksConfigError(
                f"{book_id}: live_enabled=true no está permitido en L0; los satellites "
                "operan en paper (RFC-003). Habilitar live exige ADR + gate humano"
            )

        pnl_source = entry.get("pnl_source", "manual")
        if pnl_source not in VALID_PNL_SOURCES:
            raise CapitalBooksConfigError(
                f"{book_id}.pnl_source inválido: {pnl_source!r}; "
                f"permitidos {sorted(VALID_PNL_SOURCES)}"
            )

        manual_pnl = entry.get("manual_pnl") or {}
        if not isinstance(manual_pnl, Mapping):
            raise CapitalBooksConfigError(f"{book_id}.manual_pnl debe ser un objeto")
        realized, unrealized = _parse_pnl(manual_pnl, f"{book_id}.manual_pnl")

        books.append(
            BookAllocation(
                book_id=book_id,
                engine=str(entry.get("engine", "unknown")),
                allocation_pct=pct,
                live_enabled=live_enabled,
                pnl_source=pnl_source,
                realized_pnl=realized,
                unrealized_pnl=unrealized,
            )
        )

    if total_pct != _HUNDRED:
        raise CapitalBooksConfigError(
            f"las allocations deben sumar exactamente 100 (suman {total_pct})"
        )

    books.sort(key=lambda book: KNOWN_BOOK_IDS.index(book.book_id))
    return CapitalBooksConfig(
        version=int(raw.get("version", 0)),
        contributed_capital_usd=_money(contributed),
        ops_reserve_cap_usd=_money(ops_reserve_cap),
        tradable_capital_floor_usd=tradable_floor,
        books=tuple(books),
    )


def load_capital_books_config(path: Optional[Path] = None) -> CapitalBooksConfig:
    """Carga la config versionada; `TRADABLE_CAPITAL_USD` sobreescribe el piso."""
    config_path = Path(
        path or os.getenv("CAPITAL_BOOKS_CONFIG_PATH") or _DEFAULT_CONFIG_PATH
    )
    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CapitalBooksConfigError(
            f"no se pudo leer la config de books en {config_path}: {exc}"
        )
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise CapitalBooksConfigError(
            f"config de books no es JSON válido ({config_path}): {exc}"
        )

    override = os.getenv("TRADABLE_CAPITAL_USD")
    return parse_capital_books_config(raw, tradable_capital_override=override)


def validate_capital_books_config(path: Optional[Path] = None) -> CapitalBooksConfig:
    """Alias explícito para chequeos de arranque (`validate_startup.py`)."""
    return load_capital_books_config(path=path)


def _notional_cap(tradable_floor: Decimal, allocation_pct: Decimal) -> Decimal:
    # ROUND_DOWN: un cap nunca debe redondear hacia arriba y habilitar más notional
    # del asignado.
    return _money(tradable_floor * allocation_pct / _HUNDRED, rounding=ROUND_DOWN)


def _resolved_pnl(
    book: BookAllocation, overrides: Mapping[str, Any]
) -> Tuple[Decimal, Decimal]:
    override = overrides.get(book.book_id)
    if override is None:
        return book.realized_pnl, book.unrealized_pnl
    if not isinstance(override, Mapping):
        raise CapitalBooksConfigError(
            f"pnl_overrides[{book.book_id}] debe ser un objeto con {list(_PNL_FIELDS)}"
        )
    unknown = sorted(set(override) - set(_PNL_FIELDS))
    if unknown:
        raise CapitalBooksConfigError(
            f"pnl_overrides[{book.book_id}]: campos no soportados {unknown}; "
            f"sólo {list(_PNL_FIELDS)}"
        )
    merged = {
        "realized_pnl": override.get("realized_pnl", book.realized_pnl),
        "unrealized_pnl": override.get("unrealized_pnl", book.unrealized_pnl),
    }
    return _parse_pnl(merged, f"pnl_overrides[{book.book_id}]")


def get_books_snapshot(
    *,
    config: Optional[CapitalBooksConfig] = None,
    pnl_overrides: Optional[Mapping[str, Any]] = None,
    ops_reserve_committed: Optional[Any] = None,
) -> Dict[str, Any]:
    """Snapshot consolidado: por book + totales, todo en `Decimal`.

    `pnl_overrides` permite inyectar el PnL que conoce el proceso llamante
    (`{"core_grid": {"realized_pnl": "12.34", "unrealized_pnl": "0"}}`) sin tocar la
    config versionada. Es el hook que usa el engine para el book interno mientras el
    PnL de los satellites siga siendo carga manual.

    `ops_reserve_committed` (str/Decimal) sobreescribe el devengado de ops que
    normalmente aporta el Track B; existe para tests y para callers que ya lo tienen
    resuelto. Sin él se consulta `app.core.ops_ledger`, después el env.

    El risk engine (ADR-003) evalúa kill/daily sobre `totals.consolidated_equity`, que
    se apoya en `tradable_capital` (aportado − ops devengado): un solo kill para los
    tres books, nunca uno por book (AC-S6.4).
    """
    config = config or load_capital_books_config()
    overrides = dict(pnl_overrides or {})

    unknown = sorted(set(overrides) - set(KNOWN_BOOK_IDS))
    if unknown:
        raise CapitalBooksConfigError(
            f"pnl_overrides con book_id desconocido: {unknown}; "
            f"permitidos {list(KNOWN_BOOK_IDS)}"
        )

    committed, committed_source = _resolve_ops_reserve_committed(
        config.contributed_capital_usd, ops_reserve_committed
    )
    tradable_capital = _money(config.contributed_capital_usd - committed)

    books: list[Dict[str, Any]] = []
    allocated_cap = _ZERO
    live_cap = _ZERO
    total_realized = _ZERO
    total_unrealized = _ZERO

    for book in config.books:
        cap = _notional_cap(config.tradable_capital_floor_usd, book.allocation_pct)
        realized, unrealized = _resolved_pnl(book, overrides)
        book_live_cap = cap if book.live_enabled else _ZERO

        allocated_cap += cap
        live_cap += book_live_cap
        total_realized += realized
        total_unrealized += unrealized

        books.append(
            {
                "book_id": book.book_id,
                "engine": book.engine,
                "allocation_pct": book.allocation_pct,
                "notional_cap_usd": cap,
                "live_enabled": book.live_enabled,
                "live_notional_cap_usd": book_live_cap,
                "pnl_source": book.pnl_source,
                "realized_pnl": realized,
                "unrealized_pnl": unrealized,
                "total_pnl": realized + unrealized,
            }
        )

    consolidated_pnl = total_realized + total_unrealized
    return {
        "config_version": config.version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "books": books,
        "totals": {
            "contributed_capital": config.contributed_capital_usd,
            "ops_reserve_cap": config.ops_reserve_cap_usd,
            "ops_reserve_committed": committed,
            "tradable_capital": tradable_capital,
            "tradable_capital_floor": config.tradable_capital_floor_usd,
            "allocated_notional_cap": allocated_cap,
            "live_notional_cap": live_cap,
            "realized_pnl": total_realized,
            "unrealized_pnl": total_unrealized,
            "consolidated_pnl": consolidated_pnl,
            "consolidated_equity": tradable_capital + consolidated_pnl,
        },
        "live_books": [book["book_id"] for book in books if book["live_enabled"]],
        "paper_books": [book["book_id"] for book in books if not book["live_enabled"]],
        "notional_cap_policy": NOTIONAL_CAP_POLICY,
        "ops_reserve_committed_source": committed_source,
        "ops_reserve_over_cap": committed > config.ops_reserve_cap_usd,
        "capital_note": CAPITAL_NOTE,
        "pnl_note": PNL_NOTE,
    }


def get_consolidated_equity(
    *,
    config: Optional[CapitalBooksConfig] = None,
    pnl_overrides: Optional[Mapping[str, Any]] = None,
    ops_reserve_committed: Optional[Any] = None,
) -> Decimal:
    """Equity consolidado de los tres books — entrada del risk engine (ADR-003).

    `tradable_capital + consolidated_pnl`, donde el tradable ya descuenta el ops
    devengado. Es la base del kill según CEO Amendment 01 (Decisión 1).
    """
    snapshot = get_books_snapshot(
        config=config,
        pnl_overrides=pnl_overrides,
        ops_reserve_committed=ops_reserve_committed,
    )
    return snapshot["totals"]["consolidated_equity"]


def serialize_books_snapshot(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Convierte el snapshot a JSON-safe: montos como string, nunca float."""

    def _fmt(value: Any) -> Any:
        return str(_money(value)) if isinstance(value, Decimal) else value

    return {
        "config_version": snapshot["config_version"],
        "generated_at": snapshot["generated_at"],
        "books": [
            {key: _fmt(value) for key, value in book.items()}
            for book in snapshot["books"]
        ],
        "totals": {key: _fmt(value) for key, value in snapshot["totals"].items()},
        "live_books": list(snapshot["live_books"]),
        "paper_books": list(snapshot["paper_books"]),
        "notional_cap_policy": snapshot["notional_cap_policy"],
        "ops_reserve_committed_source": snapshot["ops_reserve_committed_source"],
        "ops_reserve_over_cap": snapshot["ops_reserve_over_cap"],
        "capital_note": snapshot["capital_note"],
        "pnl_note": snapshot["pnl_note"],
    }
