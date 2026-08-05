"""P1: persistencia monte_carlo_runs."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from datetime import datetime, timezone

from app.models.backtest_run import BacktestRun
from app.models.base import Base
from app.models.monte_carlo_run import MonteCarloRun
from app.research.monte_carlo_paths import MonteCarloDrawdownStudy
from app.services.monte_carlo_persistence import persist_monte_carlo_drawdown_study


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


def test_persist_monte_carlo_inserts_row(memory_session) -> None:
    study = MonteCarloDrawdownStudy(
        seed=42,
        n_paths=8,
        horizon=10,
        baseline_max_drawdown=0.04,
        mean_max_drawdown=0.05,
        p95_max_drawdown=0.09,
        worst_max_drawdown=0.11,
        shock_single_day_gross_multiplier=None,
        shock_three_day_run_gross_multiplier=None,
        bootstrap_mode="iid",
        block_size=None,
    )
    rid = persist_monte_carlo_drawdown_study(
        memory_session,
        symbol="btcusdt",
        study=study,
        historical_returns_length=59,
    )
    memory_session.commit()
    assert rid == 1
    row = memory_session.query(MonteCarloRun).one()
    assert row.symbol == "BTCUSDT"
    assert row.p95_max_drawdown == pytest.approx(0.09)
    assert row.historical_returns_length == 59
    assert row.study_json["n_paths"] == 8


def test_persist_monte_carlo_sets_backtest_run_id(memory_session) -> None:
    tz = timezone.utc
    br = BacktestRun(
        name="for-mc-fk",
        symbol="BTCUSDT",
        strategy_hash="x",
        config_json={},
        cost_model_json={},
        started_at=datetime(2026, 5, 1, tzinfo=tz),
        finished_at=datetime(2026, 5, 2, tzinfo=tz),
        status="completed",
    )
    memory_session.add(br)
    memory_session.flush()

    study = MonteCarloDrawdownStudy(
        seed=7,
        n_paths=4,
        horizon=10,
        baseline_max_drawdown=0.04,
        mean_max_drawdown=0.05,
        p95_max_drawdown=0.09,
        worst_max_drawdown=0.11,
        shock_single_day_gross_multiplier=None,
        shock_three_day_run_gross_multiplier=None,
        bootstrap_mode="iid",
        block_size=None,
    )
    persist_monte_carlo_drawdown_study(
        memory_session,
        symbol="BTCUSDT",
        study=study,
        historical_returns_length=30,
        backtest_run_id=br.id,
    )
    memory_session.commit()
    row = memory_session.query(MonteCarloRun).one()
    assert row.backtest_run_id == br.id
