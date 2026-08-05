"""
Guardar resultados de backtest en PostgreSQL (tablas backtest_runs / backtest_metrics).

Uso opt-in vía ``BacktestConfig.persist_run_to_db`` para no escribir en BD en tests o entornos sin migración.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.models.backtest_run import BacktestMetric, BacktestRun
from app.services.backtesting_service import BacktestConfig, BacktestResult


def _float_scalar(value: Any) -> float | None:
    if value is None:
        return None
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def persist_completed_backtest_run(
    db: Session,
    *,
    name: str | None,
    baseline_config: BacktestConfig,
    sim_config: BacktestConfig,
    result: BacktestResult,
    cost_stress_meta: Mapping[str, Any],
    started_at: datetime,
    finished_at: datetime | None = None,
    status: str = "completed",
) -> int:
    """
    Inserta ``BacktestRun`` + ``BacktestMetric``. El caller hace ``commit``.

    Returns:
        id de la fila ``backtest_runs``.
    """
    if finished_at is None:
        finished_at = datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=timezone.utc)

    audit = result.metrics_json.get("transaction_cost_audit")
    cost_model_json: dict[str, Any] = {"transaction_cost_audit": audit}
    if cost_stress_meta:
        cost_model_json["cost_stress"] = dict(cost_stress_meta)

    config_json: dict[str, Any] = {
        "baseline": baseline_config.model_dump(mode="json"),
        "simulation_effective": sim_config.model_dump(mode="json"),
    }

    run = BacktestRun(
        name=name,
        symbol=result.symbol,
        strategy_hash=result.strategy_hash,
        config_json=config_json,
        cost_model_json=cost_model_json,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
    )
    db.add(run)
    db.flush()

    metrics_row = BacktestMetric(
        backtest_run_id=run.id,
        sharpe_ratio=_float_scalar(result.sharpe_ratio),
        sortino_ratio=_float_scalar(result.sortino_ratio),
        max_drawdown=_float_scalar(result.max_drawdown),
        cagr=None,
        turnover=None,
        after_cost_pnl=_float_scalar(result.total_return),
        total_return=_float_scalar(result.total_return),
        total_trades=int(result.total_trades)
        if result.total_trades is not None
        else None,
        win_rate=_float_scalar(result.win_rate),
        profit_factor=_float_scalar(result.profit_factor),
        initial_capital=_float_scalar(result.initial_capital),
        final_capital=_float_scalar(result.final_capital),
        metrics_json=dict(result.metrics_json),
    )
    db.add(metrics_row)
    db.flush()
    return int(run.id)
