"""P1: retención monte_carlo_runs por símbolo."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.monte_carlo_run import MonteCarloRun
from app.services.monte_carlo_retention import (
    prune_monte_carlo_runs_for_symbol_keep_last,
    prune_monte_carlo_runs_for_symbol_max_age_days,
)


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


def _mc_row(symbol: str, created_at: datetime, seed: int) -> MonteCarloRun:
    return MonteCarloRun(
        symbol=symbol,
        backtest_run_id=None,
        seed=seed,
        n_paths=4,
        horizon=5,
        bootstrap_mode="iid",
        block_size=None,
        shock_single_day_gross_multiplier=None,
        shock_three_day_run_gross_multiplier=None,
        baseline_max_drawdown=0.01,
        mean_max_drawdown=0.02,
        p95_max_drawdown=0.03,
        worst_max_drawdown=0.04,
        historical_returns_length=10,
        study_json={},
        created_at=created_at,
    )


def test_prune_deletes_oldest_by_created_at(memory_session) -> None:
    tz = timezone.utc
    sym = "BTCUSDT"
    days = [1, 2, 3, 4]
    for i, d in enumerate(days):
        memory_session.add(_mc_row(sym, datetime(2026, 1, d, tzinfo=tz), seed=i))
    memory_session.commit()

    deleted = prune_monte_carlo_runs_for_symbol_keep_last(
        memory_session, symbol=sym, keep_last=2
    )
    assert deleted == 2
    n = memory_session.query(MonteCarloRun).filter_by(symbol=sym).count()
    assert n == 2
    seeds = [r.seed for r in memory_session.query(MonteCarloRun).all()]
    assert set(seeds) == {2, 3}


def test_prune_max_age_days_removes_stale_rows(memory_session) -> None:
    tz = timezone.utc
    sym = "SOLUSDT"
    old = _mc_row(
        sym,
        datetime(2020, 1, 1, tzinfo=tz),
        seed=1,
    )
    recent = _mc_row(
        sym,
        datetime(2026, 5, 1, tzinfo=tz),
        seed=2,
    )
    memory_session.add_all([old, recent])
    memory_session.commit()

    ref = datetime(2026, 5, 15, tzinfo=tz)
    deleted = prune_monte_carlo_runs_for_symbol_max_age_days(
        memory_session,
        symbol=sym,
        max_age_days=30,
        reference_time=ref,
    )
    assert deleted == 1
    seeds = {r.seed for r in memory_session.query(MonteCarloRun).all()}
    assert seeds == {2}


def test_prune_max_age_zero_returns_zero(memory_session) -> None:
    memory_session.add(
        _mc_row(
            "XRPUSDT",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            seed=0,
        )
    )
    memory_session.commit()
    assert (
        prune_monte_carlo_runs_for_symbol_max_age_days(
            memory_session,
            symbol="XRPUSDT",
            max_age_days=0,
        )
        == 0
    )


def test_prune_zero_when_keep_last_below_one(memory_session) -> None:
    memory_session.add(
        _mc_row(
            "ETHUSDT",
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            seed=0,
        )
    )
    memory_session.commit()
    assert (
        prune_monte_carlo_runs_for_symbol_keep_last(
            memory_session, symbol="ETHUSDT", keep_last=0
        )
        == 0
    )
