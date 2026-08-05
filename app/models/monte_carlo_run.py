"""
Persistencia de estudios Monte Carlo drawdown (promotion gate / Fase C).
"""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.models.base import Base


class MonteCarloRun(Base):
    """Una corrida de MC ligera (bootstrap retornos) para auditoría y series temporales."""

    __tablename__ = "monte_carlo_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    backtest_run_id = Column(
        Integer,
        ForeignKey("backtest_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    seed = Column(Integer, nullable=False)
    n_paths = Column(Integer, nullable=False)
    horizon = Column(Integer, nullable=False)
    bootstrap_mode = Column(String(16), nullable=False)
    block_size = Column(Integer, nullable=True)
    shock_single_day_gross_multiplier = Column(Float, nullable=True)
    shock_three_day_run_gross_multiplier = Column(Float, nullable=True)
    baseline_max_drawdown = Column(Float, nullable=False)
    mean_max_drawdown = Column(Float, nullable=False)
    p95_max_drawdown = Column(Float, nullable=False)
    worst_max_drawdown = Column(Float, nullable=False)
    historical_returns_length = Column(Integer, nullable=True)
    study_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
