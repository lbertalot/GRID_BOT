"""
Guardar un ``MonteCarloDrawdownStudy`` en PostgreSQL (tabla ``monte_carlo_runs``).

Opt-in vía ``ML_PROMOTION_GATE_PERSIST_MC`` en el ciclo de trading; el caller hace ``commit``.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.monte_carlo_run import MonteCarloRun
from app.research.monte_carlo_paths import MonteCarloDrawdownStudy


def persist_monte_carlo_drawdown_study(
    db: Session,
    *,
    symbol: str,
    study: MonteCarloDrawdownStudy,
    historical_returns_length: int | None = None,
    backtest_run_id: int | None = None,
) -> int:
    """
    Inserta una fila ``monte_carlo_runs``.

    Returns:
        id de la fila insertada.
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        raise ValueError("symbol is required")

    payload = study.model_dump(mode="json")
    row = MonteCarloRun(
        symbol=sym,
        backtest_run_id=backtest_run_id,
        seed=int(study.seed),
        n_paths=int(study.n_paths),
        horizon=int(study.horizon),
        bootstrap_mode=str(study.bootstrap_mode),
        block_size=study.block_size,
        shock_single_day_gross_multiplier=study.shock_single_day_gross_multiplier,
        shock_three_day_run_gross_multiplier=study.shock_three_day_run_gross_multiplier,
        baseline_max_drawdown=float(study.baseline_max_drawdown),
        mean_max_drawdown=float(study.mean_max_drawdown),
        p95_max_drawdown=float(study.p95_max_drawdown),
        worst_max_drawdown=float(study.worst_max_drawdown),
        historical_returns_length=historical_returns_length,
        study_json=payload,
    )
    db.add(row)
    db.flush()
    return int(row.id)
