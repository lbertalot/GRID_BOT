"""
Carga snapshots after-cost para el promotion gate (BD o JSON de prueba).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.backtest_run import BacktestRun
from app.research.promotion_gate import AfterCostBacktestSnapshot


def after_cost_snapshot_from_json_string(raw_json: str) -> AfterCostBacktestSnapshot:
    """Parsea JSON válido hacia snapshot (tests / override operativo)."""
    data: Any = json.loads(raw_json)
    if not isinstance(data, dict):
        raise TypeError("JSON must be an object")
    return AfterCostBacktestSnapshot.model_validate(data)


def snapshot_from_completed_run(
    run: BacktestRun,
) -> Optional[AfterCostBacktestSnapshot]:
    """Construye snapshot desde un `BacktestRun` con `metrics` cargadas."""
    if run.metrics is None:
        return None
    m = run.metrics
    total_ret: Optional[float] = None
    if m.total_return is not None:
        total_ret = float(m.total_return)
    elif m.after_cost_pnl is not None:
        total_ret = float(m.after_cost_pnl)
    return AfterCostBacktestSnapshot(
        sharpe_ratio=float(m.sharpe_ratio) if m.sharpe_ratio is not None else None,
        max_drawdown=float(m.max_drawdown) if m.max_drawdown is not None else None,
        total_return=total_ret,
    )


def load_latest_after_cost_snapshot_and_run_id(
    db_session: Session,
    symbol: str,
) -> tuple[Optional[AfterCostBacktestSnapshot], Optional[int]]:
    """
    Última corrida ``completed`` para el símbolo, por ``finished_at`` descendente.

    Returns:
        ``(snapshot, backtest_run_id)``. ``backtest_run_id`` es el ``id`` de la fila
        ``backtest_runs`` usada para el snapshot (útil para enlazar ``monte_carlo_runs``).
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        return None, None
    run = (
        db_session.query(BacktestRun)
        .options(joinedload(BacktestRun.metrics))
        .filter(
            func.upper(BacktestRun.symbol) == sym,
            BacktestRun.status == "completed",
        )
        .order_by(BacktestRun.finished_at.desc())
        .first()
    )
    if run is None:
        return None, None
    snap = snapshot_from_completed_run(run)
    if snap is None:
        return None, None
    return snap, int(run.id)


def load_latest_after_cost_snapshot_for_symbol(
    db_session: Session,
    symbol: str,
) -> Optional[AfterCostBacktestSnapshot]:
    """Ver :func:`load_latest_after_cost_snapshot_and_run_id` (solo el snapshot)."""
    snap, _ = load_latest_after_cost_snapshot_and_run_id(db_session, symbol)
    return snap
