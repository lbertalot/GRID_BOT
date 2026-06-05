"""P1: carga de snapshot after-cost para promotion gate."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.backtest_run import BacktestMetric, BacktestRun
from app.models.base import Base
from app.services.backtest_gate_loader import (
    after_cost_snapshot_from_json_string,
    load_latest_after_cost_snapshot_and_run_id,
    load_latest_after_cost_snapshot_for_symbol,
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


def test_load_latest_returns_most_recent(memory_session) -> None:
    tz = timezone.utc
    older = BacktestRun(
        name="old",
        symbol="ETHUSDT",
        strategy_hash="h1",
        config_json={},
        cost_model_json={},
        started_at=datetime(2026, 1, 1, tzinfo=tz),
        finished_at=datetime(2026, 1, 2, tzinfo=tz),
        status="completed",
    )
    newer = BacktestRun(
        name="new",
        symbol="ethusdt",
        strategy_hash="h1",
        config_json={},
        cost_model_json={},
        started_at=datetime(2026, 2, 1, tzinfo=tz),
        finished_at=datetime(2026, 2, 2, tzinfo=tz),
        status="completed",
    )
    memory_session.add_all([older, newer])
    memory_session.flush()

    m_old = BacktestMetric(
        backtest_run_id=older.id,
        sharpe_ratio=0.1,
        max_drawdown=-0.2,
        total_return=0.01,
        metrics_json={},
    )
    m_new = BacktestMetric(
        backtest_run_id=newer.id,
        sharpe_ratio=1.5,
        max_drawdown=-0.08,
        total_return=0.12,
        metrics_json={},
    )
    memory_session.add_all([m_old, m_new])
    memory_session.commit()

    snap = load_latest_after_cost_snapshot_for_symbol(memory_session, "ETHUSDT")
    assert snap is not None
    assert snap.sharpe_ratio == pytest.approx(1.5)
    assert snap.max_drawdown == pytest.approx(-0.08)
    assert snap.total_return == pytest.approx(0.12)

    snap2, rid = load_latest_after_cost_snapshot_and_run_id(memory_session, "ETHUSDT")
    assert snap2 is not None
    assert snap2.sharpe_ratio == pytest.approx(1.5)
    assert rid == newer.id


def test_json_string_roundtrip() -> None:
    raw = '{"sharpe_ratio": 0.9, "max_drawdown": -0.03, "total_return": 0.04}'
    s = after_cost_snapshot_from_json_string(raw)
    assert s.sharpe_ratio == pytest.approx(0.9)
    assert s.max_drawdown == pytest.approx(-0.03)
