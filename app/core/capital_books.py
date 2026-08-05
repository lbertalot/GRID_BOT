"""Unified capital ledger — minimal multi-book view (P0 slice S6, ADR-004 / RFC-003).

Un solo pool de capital contable, tres books lógicos sobre el **capital tradable**
(aportado − reserva de ops):

    core_grid       70%  · engine GRID_BOT        · único book con live habilitado en L0
    sat_systematic  20%  · engine freqtrade       · paper/dry-run en L0
    sat_signals     10%  · engine TradingAgents   · paper en L0

Alcance L0 (ver AC-S6.5): esto es **allocations + caps + lectura**, no contabilidad
completa. El PnL de los satellites es ingest **manual/externo**: se escribe a mano en
`config/capital_books.json` (`books[].manual_pnl`) con el corte del tear sheet, o se
inyecta por `pnl_overrides` desde el proceso que ya conoce el número. El tagging de
fills por book y los adapters de freqtrade quedan para P1.

Fail-closed: cualquier config inválida levanta `CapitalBooksConfigError` en vez de
devolver números que parezcan válidos. Todo el dinero es `Decimal`; un `float` en un
campo monetario es un error, no una conversión silenciosa.

Este módulo no habilita trading real: `live_enabled` es una declaración de política y
en L0 sólo `core_grid` puede tenerla en `true`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

CORE_BOOK_ID = "core_grid"
KNOWN_BOOK_IDS: Tuple[str, ...] = ("core_grid", "sat_systematic", "sat_signals")

# L0 (gate 2026-09-06): sólo el Core Grid opera con dinero real. Los satellites
# tienen asignación declarada pero corren en paper. Cambiar esto exige ADR + gate
# humano (`.cursor/rules/40-no-live-without-gate.mdc`), no una edición de config.
L0_LIVE_ALLOWED_BOOK_IDS = frozenset({CORE_BOOK_ID})

VALID_PNL_SOURCES = frozenset({"internal", "manual"})
_PNL_FIELDS = ("realized_pnl", "unrealized_pnl")

PNL_NOTE = (
    "PnL de satellites es carga manual en L0: se edita en config/capital_books.json "
    "(books[].manual_pnl) o se inyecta vía pnl_overrides. Sólo core_grid reporta PnL "
    "interno del engine."
)

_CENTS = Decimal("0.01")
_HUNDRED = Decimal("100")

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "capital_books.json"


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
    version: int
    contributed_capital_usd: Decimal
    ops_reserve_usd: Decimal
    tradable_capital_usd: Decimal
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


def _resolve_tradable_capital(
    contributed: Decimal, ops_reserve: Decimal, override_raw: Optional[str]
) -> Decimal:
    """Capital tradable = aportado − reserva ops, salvo override explícito.

    El override nunca puede comerse la reserva de ops (AC-S5.1): la reserva no es
    capital dimensionable.
    """
    derived = contributed - ops_reserve
    if derived <= 0:
        raise CapitalBooksConfigError(
            f"capital tradable derivado no positivo: contributed={contributed} "
            f"− ops_reserve={ops_reserve} = {derived}"
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
            f"TRADABLE_CAPITAL_USD={override} excede el máximo tradable {derived} "
            f"(contributed {contributed} − ops_reserve {ops_reserve}); "
            "la reserva de ops no es capital tradable"
        )
    return _money(override)


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
    """Valida la config cruda (JSON versionado) y devuelve el modelo tipado."""
    if not isinstance(raw, Mapping):
        raise CapitalBooksConfigError("la config de books debe ser un objeto JSON")

    raw_books = raw.get("books")
    if not isinstance(raw_books, list) or not raw_books:
        raise CapitalBooksConfigError("la config no declara books")

    contributed = _to_decimal(
        raw.get("contributed_capital_usd", "0"), "contributed_capital_usd"
    )
    ops_reserve = _to_decimal(raw.get("ops_reserve_usd", "0"), "ops_reserve_usd")
    if contributed <= 0:
        raise CapitalBooksConfigError(
            f"contributed_capital_usd debe ser > 0 (recibido {contributed})"
        )
    if ops_reserve < 0:
        raise CapitalBooksConfigError(
            f"ops_reserve_usd no puede ser negativo (recibido {ops_reserve})"
        )

    tradable = _resolve_tradable_capital(
        contributed, ops_reserve, tradable_capital_override
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
        ops_reserve_usd=_money(ops_reserve),
        tradable_capital_usd=tradable,
        books=tuple(books),
    )


def load_capital_books_config(path: Optional[Path] = None) -> CapitalBooksConfig:
    """Carga la config versionada; `TRADABLE_CAPITAL_USD` sobreescribe el tradable."""
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
        raise CapitalBooksConfigError(f"config de books no es JSON válido ({config_path}): {exc}")

    override = os.getenv("TRADABLE_CAPITAL_USD")
    return parse_capital_books_config(raw, tradable_capital_override=override)


def validate_capital_books_config(path: Optional[Path] = None) -> CapitalBooksConfig:
    """Alias explícito para chequeos de arranque (`validate_startup.py`)."""
    return load_capital_books_config(path=path)


def _notional_cap(tradable: Decimal, allocation_pct: Decimal) -> Decimal:
    # ROUND_DOWN: un cap nunca debe redondear hacia arriba y habilitar más notional
    # del asignado.
    return _money(tradable * allocation_pct / _HUNDRED, rounding=ROUND_DOWN)


def _resolved_pnl(
    book: BookAllocation, overrides: Mapping[str, Any]
) -> Tuple[Decimal, Decimal]:
    override = overrides.get(book.book_id)
    if override is None:
        return book.realized_pnl, book.unrealized_pnl
    if not isinstance(override, Mapping):
        raise CapitalBooksConfigError(
            f"pnl_overrides[{book.book_id}] debe ser un objeto con "
            f"{list(_PNL_FIELDS)}"
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
) -> Dict[str, Any]:
    """Snapshot consolidado: por book + totales, todo en `Decimal`.

    `pnl_overrides` permite inyectar el PnL que conoce el proceso llamante
    (`{"core_grid": {"realized_pnl": "12.34", "unrealized_pnl": "0"}}`) sin tocar la
    config versionada. Es el hook que usa el engine para el book interno mientras el
    PnL de los satellites siga siendo carga manual.

    El risk engine (ADR-003) evalúa kill/daily sobre `totals.consolidated_equity`:
    un solo kill para los tres books, nunca uno por book (AC-S6.4).
    """
    config = config or load_capital_books_config()
    overrides = dict(pnl_overrides or {})

    unknown = sorted(set(overrides) - set(KNOWN_BOOK_IDS))
    if unknown:
        raise CapitalBooksConfigError(
            f"pnl_overrides con book_id desconocido: {unknown}; "
            f"permitidos {list(KNOWN_BOOK_IDS)}"
        )

    books: list[Dict[str, Any]] = []
    allocated_cap = Decimal("0.00")
    live_cap = Decimal("0.00")
    total_realized = Decimal("0.00")
    total_unrealized = Decimal("0.00")

    for book in config.books:
        cap = _notional_cap(config.tradable_capital_usd, book.allocation_pct)
        realized, unrealized = _resolved_pnl(book, overrides)
        book_live_cap = cap if book.live_enabled else Decimal("0.00")

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
            "ops_reserve": config.ops_reserve_usd,
            "tradable_capital": config.tradable_capital_usd,
            "allocated_notional_cap": allocated_cap,
            "live_notional_cap": live_cap,
            "realized_pnl": total_realized,
            "unrealized_pnl": total_unrealized,
            "consolidated_pnl": consolidated_pnl,
            "consolidated_equity": config.tradable_capital_usd + consolidated_pnl,
        },
        "live_books": [book["book_id"] for book in books if book["live_enabled"]],
        "paper_books": [book["book_id"] for book in books if not book["live_enabled"]],
        "pnl_note": PNL_NOTE,
    }


def get_consolidated_equity(
    *,
    config: Optional[CapitalBooksConfig] = None,
    pnl_overrides: Optional[Mapping[str, Any]] = None,
) -> Decimal:
    """Equity consolidado de los tres books — entrada del risk engine (ADR-003)."""
    snapshot = get_books_snapshot(config=config, pnl_overrides=pnl_overrides)
    return snapshot["totals"]["consolidated_equity"]


def serialize_books_snapshot(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Convierte el snapshot a JSON-safe: montos como string, nunca float."""
    def _fmt(value: Any) -> Any:
        return str(_money(value)) if isinstance(value, Decimal) else value

    return {
        "config_version": snapshot["config_version"],
        "generated_at": snapshot["generated_at"],
        "books": [{key: _fmt(value) for key, value in book.items()} for book in snapshot["books"]],
        "totals": {key: _fmt(value) for key, value in snapshot["totals"].items()},
        "live_books": list(snapshot["live_books"]),
        "paper_books": list(snapshot["paper_books"]),
        "pnl_note": snapshot["pnl_note"],
    }
