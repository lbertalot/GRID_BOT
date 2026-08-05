"""Tests P1: helper de gate en trading_tasks (sin Celery ni TensorFlow)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.backtest_run import BacktestMetric, BacktestRun
from app.models.base import Base
from app.models.monte_carlo_run import MonteCarloRun


@pytest.fixture(autouse=True)
def celery_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")


def _flat_klines(n: int = 60) -> list[list[float]]:
    return [[0, 100.0, 100.0, 100.0, 100.0, 1.0] for _ in range(n)]


@pytest.mark.asyncio
async def test_promotion_gate_disabled_allows_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ML_PROMOTION_GATE_ENABLED", raising=False)
    import app.services.trading_tasks as tt

    ok, reasons = await tt._promotion_gate_allows_ml("ETHUSDT", _flat_klines())
    assert ok is True
    assert reasons == ()


@pytest.mark.asyncio
async def test_promotion_gate_blocks_flat_klines_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_BLOCK_FLAT", "true")
    import app.services.trading_tasks as tt

    ok, reasons = await tt._promotion_gate_allows_ml("ETHUSDT", _flat_klines())
    assert ok is False
    assert "tqs_direction_flat" in reasons


@pytest.mark.asyncio
async def test_promotion_gate_skips_when_too_few_bars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    import app.services.trading_tasks as tt

    short = _flat_klines(n=10)
    ok, reasons = await tt._promotion_gate_allows_ml("ETHUSDT", short)
    assert ok is True
    assert reasons == ()


def _uptrend_klines(n: int = 60) -> list[list[float]]:
    return [[0, 100.0 + i * 0.2, 0, 0, 100.0 + i * 0.2, 1.0] for i in range(n)]


@pytest.mark.asyncio
async def test_promotion_gate_uses_json_backtest_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_BLOCK_FLAT", "false")
    monkeypatch.setenv("ML_PROMOTION_GATE_MIN_SHARPE_AFTER_COST", "0.5")
    monkeypatch.setenv(
        "ML_PROMOTION_GATE_BACKTEST_SNAPSHOT_JSON",
        '{"sharpe_ratio": 1.2, "max_drawdown": -0.05}',
    )
    import app.services.trading_tasks as tt

    ok, reasons = await tt._promotion_gate_allows_ml("BTCUSDT", _uptrend_klines())
    assert ok is True
    assert reasons == ()


@pytest.mark.asyncio
async def test_promotion_gate_blocks_low_sharpe_from_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_BLOCK_FLAT", "false")
    monkeypatch.setenv("ML_PROMOTION_GATE_MIN_SHARPE_AFTER_COST", "2.0")
    monkeypatch.setenv(
        "ML_PROMOTION_GATE_BACKTEST_SNAPSHOT_JSON",
        '{"sharpe_ratio": 0.1, "max_drawdown": -0.05}',
    )
    import app.services.trading_tasks as tt

    ok, reasons = await tt._promotion_gate_allows_ml("BTCUSDT", _uptrend_klines())
    assert ok is False
    assert "after_cost_sharpe_below_min" in reasons


@pytest.mark.asyncio
async def test_promotion_gate_uses_persisted_backtest_from_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SessionLocal apuntando a SQLite :memory: con una corrida completada."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    tz = timezone.utc
    run = BacktestRun(
        name="persisted-for-gate",
        symbol="BTCUSDT",
        strategy_hash="pytest",
        config_json={},
        cost_model_json={},
        started_at=datetime(2026, 3, 1, tzinfo=tz),
        finished_at=datetime(2026, 3, 2, tzinfo=tz),
        status="completed",
    )
    s.add(run)
    s.flush()
    s.add(
        BacktestMetric(
            backtest_run_id=run.id,
            sharpe_ratio=1.4,
            max_drawdown=-0.06,
            total_return=0.07,
            metrics_json={},
        )
    )
    s.commit()
    s.close()

    monkeypatch.setattr("app.db.session.SessionLocal", factory)
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_BLOCK_FLAT", "false")
    monkeypatch.setenv("ML_PROMOTION_GATE_USE_PERSISTED_BACKTEST", "true")
    monkeypatch.delenv("ML_PROMOTION_GATE_BACKTEST_SNAPSHOT_JSON", raising=False)
    monkeypatch.setenv("ML_PROMOTION_GATE_MIN_SHARPE_AFTER_COST", "0.5")

    import app.services.trading_tasks as tt

    ok, reasons = await tt._promotion_gate_allows_ml("btcusdt", _uptrend_klines())
    assert ok is True
    assert reasons == ()


@pytest.mark.asyncio
async def test_promotion_gate_persisted_backtest_low_sharpe_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    tz = timezone.utc
    run = BacktestRun(
        name="low-sharpe",
        symbol="ETHUSDT",
        strategy_hash="pytest",
        config_json={},
        cost_model_json={},
        started_at=datetime(2026, 4, 1, tzinfo=tz),
        finished_at=datetime(2026, 4, 2, tzinfo=tz),
        status="completed",
    )
    s.add(run)
    s.flush()
    s.add(
        BacktestMetric(
            backtest_run_id=run.id,
            sharpe_ratio=0.05,
            max_drawdown=-0.02,
            total_return=0.01,
            metrics_json={},
        )
    )
    s.commit()
    s.close()

    monkeypatch.setattr("app.db.session.SessionLocal", factory)
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_BLOCK_FLAT", "false")
    monkeypatch.setenv("ML_PROMOTION_GATE_USE_PERSISTED_BACKTEST", "true")
    monkeypatch.delenv("ML_PROMOTION_GATE_BACKTEST_SNAPSHOT_JSON", raising=False)
    monkeypatch.setenv("ML_PROMOTION_GATE_MIN_SHARPE_AFTER_COST", "1.0")

    import app.services.trading_tasks as tt

    ok, reasons = await tt._promotion_gate_allows_ml("ETHUSDT", _uptrend_klines())
    assert ok is False
    assert "after_cost_sharpe_below_min" in reasons


@pytest.mark.asyncio
async def test_promotion_gate_persists_monte_carlo_when_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr("app.db.session.SessionLocal", factory)
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_BLOCK_FLAT", "false")
    monkeypatch.setenv("ML_PROMOTION_GATE_PERSIST_MC", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_MC_PATHS", "8")
    monkeypatch.setenv("ML_PROMOTION_GATE_MC_HORIZON", "15")

    import app.services.trading_tasks as tt

    ok, _ = await tt._promotion_gate_allows_ml("SOLUSDT", _uptrend_klines(n=80))
    assert ok is True
    s = factory()
    try:
        rows = s.query(MonteCarloRun).all()
        assert len(rows) == 1
        assert rows[0].symbol == "SOLUSDT"
        assert rows[0].n_paths == 8
        assert rows[0].horizon == 15
    finally:
        s.close()


@pytest.mark.asyncio
async def test_promotion_gate_monte_carlo_persist_links_backtest_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    tz = timezone.utc
    run = BacktestRun(
        name="link-mc",
        symbol="BTCUSDT",
        strategy_hash="pytest",
        config_json={},
        cost_model_json={},
        started_at=datetime(2026, 5, 10, tzinfo=tz),
        finished_at=datetime(2026, 5, 11, tzinfo=tz),
        status="completed",
    )
    s.add(run)
    s.flush()
    s.add(
        BacktestMetric(
            backtest_run_id=run.id,
            sharpe_ratio=1.1,
            max_drawdown=-0.04,
            total_return=0.05,
            metrics_json={},
        )
    )
    s.commit()
    run_id = int(run.id)
    s.close()

    monkeypatch.setattr("app.db.session.SessionLocal", factory)
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_BLOCK_FLAT", "false")
    monkeypatch.setenv("ML_PROMOTION_GATE_USE_PERSISTED_BACKTEST", "true")
    monkeypatch.delenv("ML_PROMOTION_GATE_BACKTEST_SNAPSHOT_JSON", raising=False)
    monkeypatch.setenv("ML_PROMOTION_GATE_PERSIST_MC", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_MC_PATHS", "8")
    monkeypatch.setenv("ML_PROMOTION_GATE_MC_HORIZON", "12")

    import app.services.trading_tasks as tt

    ok, _ = await tt._promotion_gate_allows_ml("BTCUSDT", _uptrend_klines(n=80))
    assert ok is True
    s2 = factory()
    try:
        rows = s2.query(MonteCarloRun).all()
        assert len(rows) == 1
        assert rows[0].backtest_run_id == run_id
    finally:
        s2.close()


@pytest.mark.asyncio
async def test_promotion_gate_nlp_stub_blocks_when_below_min(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_BLOCK_FLAT", "false")
    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_MIN_SCORE", "-0.2")
    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_STUB_SCORE", "-0.9")

    async def fake_get(_key: str):
        return None

    monkeypatch.setattr("app.core.redis_cache.redis_cache.get", fake_get)
    import app.services.trading_tasks as tt

    ok, reasons = await tt._promotion_gate_allows_ml("BTCUSDT", _uptrend_klines())
    assert ok is False
    assert "nlp_sentiment_below_min" in reasons


@pytest.mark.asyncio
async def test_promotion_gate_nlp_allows_when_stub_above_min(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_BLOCK_FLAT", "false")
    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_ENABLED", "true")
    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_MIN_SCORE", "-0.5")
    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_STUB_SCORE", "0.1")

    async def fake_get(_key: str):
        return None

    monkeypatch.setattr("app.core.redis_cache.redis_cache.get", fake_get)
    import app.services.trading_tasks as tt

    ok, reasons = await tt._promotion_gate_allows_ml("BTCUSDT", _uptrend_klines())
    assert ok is True
    assert reasons == ()
