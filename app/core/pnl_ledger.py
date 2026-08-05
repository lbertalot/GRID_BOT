"""Facade de PnL MTD para el CEO overview (Wave B4 / ADR-005).

No es un ledger contable multi-book (eso sigue siendo ADR-004 capital books).
Aquí solo se expone `get_pnl_summary()` que el adaptador CEO ya espera en
`app.core.pnl_ledger`, calculando **PnL MTD mark-to-market** desde la serie
paper (`PaperEquitySeries` / S10).

Reglas:
- Dinero en `Decimal` (regla 10-financial-integrity).
- Sin serie o sin ancla usable → `PnlUnavailableError` (CEO → `unavailable`).
- Nunca devolver cero fabricado cuando faltan datos.
- Paper-safe: solo lectura de telemetría; no toca live ni órdenes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.core.paper_equity_ledger import (
    PaperEquitySeries,
    get_paper_equity_series,
    to_money,
)

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


class PnlUnavailableError(Exception):
    """Razón segura y honesta para el widget CEO (sin secrets en el mensaje)."""

    ceo_reason_safe = True


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _normalize(value: Decimal) -> Decimal:
    normalized = value.normalize()
    exponent = normalized.as_tuple().exponent
    if isinstance(exponent, int) and exponent > 0:
        normalized = normalized.quantize(Decimal(1))
    return normalized


def _equity_path(series: PaperEquitySeries) -> List[Tuple[datetime, Decimal]]:
    """Serie (at, equity) ordenada — lee samples públicos, no inventa puntos."""
    path: List[Tuple[datetime, Decimal]] = []
    for sample in series.samples:
        raw_at = sample.get("at")
        raw_eq = sample.get("equity")
        if raw_at is None or raw_eq is None:
            continue
        path.append(
            (
                _as_utc(datetime.fromisoformat(str(raw_at))),
                to_money(raw_eq, field_name="equity"),
            )
        )
    path.sort(key=lambda item: item[0])
    return path


def _month_start_utc(moment: datetime) -> datetime:
    moment = _as_utc(moment)
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _daily_pnl_fraction(series: PaperEquitySeries) -> Optional[Decimal]:
    """Último retorno diario sobre cierres 00:00 UTC, o None si no hay pares."""
    closes = series.daily_closes()
    if len(closes) < 2:
        return None
    (_, previous), (_, current) = closes[-2], closes[-1]
    if previous == ZERO:
        return None
    return _normalize(current / previous - 1)


def compute_pnl_from_series(
    series: PaperEquitySeries,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Calcula PnL MTD MtM: `E_as_of − E_start` en el mes calendario UTC.

    Ancla de inicio:
    1. último sample con `at <= month_start`, si existe;
    2. si no, el primer sample del mes (solo si hay un sample posterior).

    Sin samples, o con un único punto usable → `PnlUnavailableError`.
    """
    moment = _as_utc(now or datetime.now(timezone.utc))
    month_start = _month_start_utc(moment)
    path = _equity_path(series)

    if not path:
        raise PnlUnavailableError("sin serie equity MtM paper (0 samples)")

    before_or_at = [(t, e) for t, e in path if t <= month_start]
    in_or_after_month = [(t, e) for t, e in path if t >= month_start]

    if before_or_at:
        start_at, equity_start = before_or_at[-1]
        anchor = "pre_month_or_eom"
    elif in_or_after_month:
        start_at, equity_start = in_or_after_month[0]
        anchor = "first_in_month"
    else:
        raise PnlUnavailableError(
            "sin samples MtM en el mes calendario UTC en curso"
        )

    as_of_at, equity_as_of = path[-1]
    if as_of_at < month_start:
        raise PnlUnavailableError("serie MtM sin samples en el mes en curso")

    if as_of_at <= start_at:
        raise PnlUnavailableError(
            "serie MtM insuficiente: se necesita al menos un sample posterior "
            "al ancla MTD"
        )

    pnl_mtd = _normalize(equity_as_of - equity_start)
    daily = _daily_pnl_fraction(series)

    return {
        "pnl_mtd": pnl_mtd,
        "daily_pnl_pct": daily,
        "equity_start": equity_start,
        "equity_as_of": equity_as_of,
        "start_at": start_at.isoformat(),
        "as_of": as_of_at.isoformat(),
        "month_start": month_start.isoformat(),
        "anchor": anchor,
        "basis": "mtm_equity_series",
        "samples_used": len(path),
    }


def get_pnl_summary(
    *,
    now: Optional[datetime] = None,
    series: Optional[PaperEquitySeries] = None,
) -> Dict[str, Any]:
    """Facade para el adaptador CEO (`app.core.ceo_overview` / ADR-005).

    Contrato mínimo del payload:
    - `pnl_mtd` (Decimal): delta MtM del mes UTC en curso
    - `daily_pnl_pct` (Decimal | None): último r_t diario si hay ≥2 cierres
    - `as_of` (ISO UTC): timestamp del equity de cierre usado
    """
    target = series if series is not None else get_paper_equity_series()
    raw = compute_pnl_from_series(target, now=now)
    return {
        "pnl_mtd": raw["pnl_mtd"],
        "daily_pnl_pct": raw["daily_pnl_pct"],
        "as_of": raw["as_of"],
        "equity_start": raw["equity_start"],
        "equity_as_of": raw["equity_as_of"],
        "basis": raw["basis"],
        "anchor": raw["anchor"],
        "month_start": raw["month_start"],
    }


__all__ = [
    "PnlUnavailableError",
    "compute_pnl_from_series",
    "get_pnl_summary",
]
