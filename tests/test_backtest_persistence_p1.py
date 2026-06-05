"""P1: persistencia backtest_runs / backtest_metrics."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.backtest_run import BacktestMetric, BacktestRun
from app.models.base import Base
from app.services.backtesting_service import BacktestConfig, BacktestResult
from app.services.backtest_persistence import persist_completed_backtest_run


@pytest.fixture
def memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_persist_creates_run_and_metrics(memory_session) -> None:
    baseline = BacktestConfig(persist_run_to_db=False, spread_bps=3.0)
    sim = baseline.model_copy(update={"spread_bps": 10.0, "slippage": 0.001})
    result = BacktestResult(
        symbol="BTCUSDT",
        strategy_hash="GRID_TRADING",
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 2, 1, tzinfo=timezone.utc),
        initial_capital=10000.0,
        final_capital=10500.0,
        total_return=0.05,
        max_drawdown=-0.02,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        win_rate=0.55,
        profit_factor=1.3,
        total_trades=42,
        avg_trade_duration=2.0,
        metrics_json={
            "total_return": 0.05,
            "transaction_cost_audit": {"total_friction_usdt": "1.5"},
        },
    )
    t0 = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)
    rid = persist_completed_backtest_run(
        memory_session,
        name="pytest-run",
        baseline_config=baseline,
        sim_config=sim,
        result=result,
        cost_stress_meta={"cost_stress_two_sigma": True},
        started_at=t0,
        finished_at=datetime(2026, 5, 3, 12, 1, 0, tzinfo=timezone.utc),
    )
    memory_session.commit()
    assert rid == 1

    run = memory_session.query(BacktestRun).filter_by(id=rid).one()
    assert run.symbol == "BTCUSDT"
    assert run.status == "completed"
    assert run.cost_model_json["cost_stress"]["cost_stress_two_sigma"] is True
    assert "baseline" in run.config_json

    m = memory_session.query(BacktestMetric).filter_by(backtest_run_id=rid).one()
    assert m.sharpe_ratio == pytest.approx(1.2)
    assert m.total_trades == 42
    assert m.metrics_json["total_return"] == pytest.approx(0.05)
