"""
Persistencia de corridas de backtest (protocolo Passive Income §D backtest_runs / backtest_metrics).
"""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class BacktestRun(Base):
    """
    Una corrida de backtest: configuración + modelo de costes para auditoría after-cost.
    """

    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(256), nullable=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    strategy_hash = Column(String(64), nullable=False, index=True)
    config_json = Column(JSON, nullable=False)
    cost_model_json = Column(JSON, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), nullable=False, default="completed")

    metrics = relationship(
        "BacktestMetric",
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )


class BacktestMetric(Base):
    """Métricas escalares por corrida + snapshot JSON completo."""

    __tablename__ = "backtest_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    backtest_run_id = Column(
        Integer,
        ForeignKey("backtest_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    cagr = Column(Float, nullable=True)
    turnover = Column(Float, nullable=True)
    after_cost_pnl = Column(Float, nullable=True)
    total_return = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    initial_capital = Column(Float, nullable=True)
    final_capital = Column(Float, nullable=True)
    metrics_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    run = relationship("BacktestRun", back_populates="metrics")
