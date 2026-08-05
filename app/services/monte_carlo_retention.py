"""
Retención por símbolo para ``monte_carlo_runs`` (evitar crecimiento ilimitado).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.monte_carlo_run import MonteCarloRun

logger = logging.getLogger(__name__)


def prune_monte_carlo_runs_for_symbol_max_age_days(
    db: Session,
    *,
    symbol: str,
    max_age_days: int,
    reference_time: datetime | None = None,
) -> int:
    """
    Elimina filas con ``created_at`` estrictamente anterior a ``reference_time - max_age_days``.

    ``reference_time`` debe ser timezone-aware (UTC). Por defecto ``datetime.now(timezone.utc)``.
    """
    if max_age_days < 1:
        return 0
    sym = (symbol or "").strip().upper()
    if not sym:
        return 0
    ref = reference_time if reference_time is not None else datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    cutoff = ref - timedelta(days=max_age_days)
    deleted = (
        db.query(MonteCarloRun)
        .filter(MonteCarloRun.symbol == sym, MonteCarloRun.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    logger.debug(
        "Monte Carlo retention TTL prune",
        extra={"symbol": sym, "deleted": deleted, "max_age_days": max_age_days},
    )
    return int(deleted)


def prune_monte_carlo_runs_for_symbol_keep_last(
    db: Session,
    *,
    symbol: str,
    keep_last: int,
) -> int:
    """
    Elimina filas más antiguas que las ``keep_last`` más recientes (por ``created_at``, ``id``).

    Returns:
        Cantidad de filas borradas.
    """
    if keep_last < 1:
        return 0
    sym = (symbol or "").strip().upper()
    if not sym:
        return 0

    stale_ids = [
        row[0]
        for row in (
            db.query(MonteCarloRun.id)
            .filter(MonteCarloRun.symbol == sym)
            .order_by(MonteCarloRun.created_at.desc(), MonteCarloRun.id.desc())
            .offset(keep_last)
            .all()
        )
    ]
    if not stale_ids:
        return 0

    deleted = (
        db.query(MonteCarloRun)
        .filter(MonteCarloRun.id.in_(stale_ids))
        .delete(synchronize_session=False)
    )
    logger.debug(
        "Monte Carlo retention prune",
        extra={"symbol": sym, "deleted": deleted, "keep_last": keep_last},
    )
    return int(deleted)
