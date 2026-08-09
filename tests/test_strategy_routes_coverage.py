"""Cobertura paper-safe de app.api.strategy_routes (≥85% líneas).

Mock de RiskManager / ML / StrategySelector / BacktestingService.
Sin TensorFlow ni Binance real.
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("USE_REAL_BINANCE", "0")
os.environ.setdefault("PAPER_TRADING", "true")
os.environ.setdefault("FORCE_REAL_MODE", "false")
os.environ.setdefault("TRADING_ENABLED", "false")

from app.api import strategy_routes as sr
from app.core.risk_manager import BreakerState, MarketRegime, RegimePrediction
from app.services.backtesting_service import BacktestResult
from app.services.strategy_selector import (
    AccountState,
    StrategyParams,
    StrategySpec,
    StrategyType,
)


def _account_payload() -> dict:
    return {
        "total_equity": "10000",
        "available_balance": "5000",
        "total_exposure": "0.1",
        "daily_pnl": "0.01",
        "max_drawdown": "0.02",
        "risk_score": "0.3",
    }


def _regime() -> RegimePrediction:
    return RegimePrediction(
        long_regime=MarketRegime.RANGE,
        short_regime=MarketRegime.RANGE,
        long_conf=Decimal("0.6"),
        short_conf=Decimal("0.55"),
    )


def _strategy_spec() -> StrategySpec:
    return StrategySpec(
        strategy_name=StrategyType.GRID_TRADING,
        params=StrategyParams(
            grid_spacing_bps=50, grid_levels=10, order_size_usdt=Decimal("50")
        ),
        confidence=Decimal("0.7"),
        reasoning="test",
        regime_prediction=_regime(),
    )


def _backtest_result(*, max_dd: float = 0.05) -> BacktestResult:
    return BacktestResult(
        symbol="BTCUSDT",
        strategy_hash="abc",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 8),
        initial_capital=10000.0,
        final_capital=10500.0,
        total_return=0.05,
        max_drawdown=max_dd,
        sharpe_ratio=1.2,
        sortino_ratio=1.1,
        win_rate=0.55,
        profit_factor=1.3,
        total_trades=10,
        avg_trade_duration=60.0,
        metrics_json={"sharpe": 1.2},
    )


@pytest.fixture
def paper_env(monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("EMERGENCY_STOP", "false")


@pytest.fixture
def deps(paper_env):
    risk = MagicMock()
    risk.check_circuit_breaker.return_value = BreakerState.NORMAL
    risk.emergency_stop = False

    ml = MagicMock()
    ml.predict_regime = AsyncMock(return_value=_regime())
    ml.last_predictions = {}
    ml.get_model_status.side_effect = lambda sym: {
        "symbol": sym,
        "deep_model_loaded": False,
        "river_model_initialized": False,
        "last_prediction": None,
    }
    ml.train_deep_model = AsyncMock()

    selector = MagicMock()
    selector.select_strategy.return_value = _strategy_spec()

    bt = MagicMock()
    bt.run_backtest = AsyncMock(return_value=_backtest_result())
    bt.run_walk_forward_backtest = AsyncMock(
        return_value=[_backtest_result(), _backtest_result()]
    )
    bt.get_backtest_summary.return_value = {"avg_sharpe": 1.2}
    bt.backtest_results = [_backtest_result()]

    return {
        "risk": risk,
        "ml": ml,
        "selector": selector,
        "bt": bt,
    }


@pytest.fixture
def client(deps):
    app = FastAPI()
    app.include_router(sr.router)
    app.dependency_overrides[sr.get_risk_manager] = lambda: deps["risk"]
    app.dependency_overrides[sr.get_ml_engine] = lambda: deps["ml"]
    app.dependency_overrides[sr.get_strategy_selector] = lambda: deps["selector"]
    app.dependency_overrides[sr.get_backtesting_service] = lambda: deps["bt"]
    with TestClient(app) as c:
        c._deps = deps  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()


def test_execute_intelligent_paper_happy(client):
    r = client.post(
        "/api/v2/strategies/execute_intelligent",
        json={
            "symbol": "BTCUSDT",
            "account_state": _account_payload(),
            "paper_mode": True,
            "quick_backtest": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["paper_mode"] is True
    assert body["data"]["execution_enqueued"] is False
    assert body["data"]["backtest_passed"] is True


def test_execute_intelligent_skip_quick_backtest(client):
    r = client.post(
        "/api/v2/strategies/execute_intelligent",
        json={
            "symbol": "ETHUSDT",
            "account_state": _account_payload(),
            "paper_mode": True,
            "quick_backtest": False,
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["backtest_metrics"] == {}


def test_execute_intelligent_circuit_breaker(client):
    client._deps["risk"].check_circuit_breaker.return_value = BreakerState.DANGER
    client._deps["risk"].emergency_stop = True
    r = client.post(
        "/api/v2/strategies/execute_intelligent",
        json={
            "symbol": "BTCUSDT",
            "account_state": _account_payload(),
            "paper_mode": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["success"] is False
    assert "Circuit breaker" in r.json()["message"]


def test_execute_intelligent_excessive_drawdown(client):
    client._deps["bt"].run_backtest = AsyncMock(
        return_value=_backtest_result(max_dd=0.25)
    )
    r = client.post(
        "/api/v2/strategies/execute_intelligent",
        json={
            "symbol": "BTCUSDT",
            "account_state": _account_payload(),
            "paper_mode": True,
            "quick_backtest": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["success"] is False
    assert "drawdown" in r.json()["message"]


def test_execute_intelligent_backtest_exception_continues(client):
    client._deps["bt"].run_backtest = AsyncMock(side_effect=RuntimeError("bt fail"))
    r = client.post(
        "/api/v2/strategies/execute_intelligent",
        json={
            "symbol": "BTCUSDT",
            "account_state": _account_payload(),
            "paper_mode": True,
            "quick_backtest": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["backtest_passed"] is False
    assert "error" in r.json()["data"]["backtest_metrics"]


def test_execute_intelligent_rejects_live_without_gate(client, monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    r = client.post(
        "/api/v2/strategies/execute_intelligent",
        json={
            "symbol": "BTCUSDT",
            "account_state": _account_payload(),
            "paper_mode": False,
            "quick_backtest": False,
        },
    )
    assert r.status_code == 403
    assert "Live strategy execution rejected" in r.json()["detail"]


def test_execute_intelligent_validation_error(client):
    r = client.post(
        "/api/v2/strategies/execute_intelligent",
        json={"symbol": "BTCUSDT"},  # missing account_state
    )
    assert r.status_code == 422


def test_execute_intelligent_500_on_unexpected(client):
    client._deps["ml"].predict_regime = AsyncMock(side_effect=RuntimeError("ml boom"))
    # predict_regime in real engine swallows; our mock raises → outer 500
    r = client.post(
        "/api/v2/strategies/execute_intelligent",
        json={
            "symbol": "BTCUSDT",
            "account_state": _account_payload(),
            "paper_mode": True,
            "quick_backtest": False,
        },
    )
    assert r.status_code == 500


def test_last_decision_mock_and_cached(client):
    r = client.get("/api/v2/strategies/last_decision", params={"symbol": "BTCUSDT"})
    assert r.status_code == 200
    assert r.json()["success"] is True

    client._deps["ml"].last_predictions["ETHUSDT"] = _regime()
    r2 = client.get("/api/v2/strategies/last_decision", params={"symbol": "ETHUSDT"})
    assert r2.status_code == 200
    assert r2.json()["data"]["symbol"] == "ETHUSDT"


def test_last_decision_error(client):
    client._deps["selector"].select_strategy.side_effect = RuntimeError("sel")
    r = client.get("/api/v2/strategies/last_decision", params={"symbol": "X"})
    assert r.status_code == 500


def test_backtest_run_walk_forward(client):
    payload = {
        "symbol": "BTCUSDT",
        "strategy_spec": {
            "strategy_name": "GridTrading",
            "params": {
                "grid_spacing_bps": 50,
                "grid_levels": 10,
                "order_size_usdt": "50",
            },
            "confidence": "0.7",
            "reasoning": "unit",
            "regime_prediction": {
                "long_regime": "RANGE",
                "short_regime": "RANGE",
                "long_conf": "0.5",
                "short_conf": "0.5",
            },
        },
        "start_date": "2026-01-01T00:00:00",
        "end_date": "2026-01-31T00:00:00",
        "walk_forward": True,
    }
    r = client.post("/api/v2/strategies/backtest/run", json=payload)
    assert r.status_code == 200
    assert r.json()["data"]["results_count"] == 2


def test_backtest_run_single(client):
    payload = {
        "symbol": "BTCUSDT",
        "strategy_spec": {
            "strategy_name": "GridTrading",
            "params": {"grid_levels": 8},
            "confidence": "0.6",
            "reasoning": "unit",
            "regime_prediction": {
                "long_regime": "RANGE",
                "short_regime": "RANGE",
                "long_conf": "0.5",
                "short_conf": "0.5",
            },
        },
        "start_date": "2026-01-01T00:00:00",
        "end_date": "2026-01-08T00:00:00",
        "walk_forward": False,
        "initial_capital": 5000.0,
    }
    r = client.post("/api/v2/strategies/backtest/run", json=payload)
    assert r.status_code == 200
    assert r.json()["data"]["results_count"] == 1


def test_backtest_run_error(client):
    client._deps["bt"].run_walk_forward_backtest = AsyncMock(
        side_effect=RuntimeError("wf")
    )
    payload = {
        "symbol": "BTCUSDT",
        "strategy_spec": {
            "strategy_name": "HOLD",
            "params": {},
            "confidence": "0.5",
            "reasoning": "x",
            "regime_prediction": {
                "long_regime": "RANGE",
                "short_regime": "RANGE",
                "long_conf": "0.5",
                "short_conf": "0.5",
            },
        },
        "start_date": "2026-01-01T00:00:00",
        "end_date": "2026-01-02T00:00:00",
        "walk_forward": True,
    }
    r = client.post("/api/v2/strategies/backtest/run", json=payload)
    assert r.status_code == 500


def test_backtest_results_filters(client):
    other = _backtest_result()
    other.symbol = "ETHUSDT"
    other.strategy_hash = "zzz"
    client._deps["bt"].backtest_results = [_backtest_result(), other]

    r = client.get(
        "/api/v2/strategies/backtest/results",
        params={"symbol": "BTCUSDT", "strategy": "abc", "limit": 5},
    )
    assert r.status_code == 200
    assert r.json()["data"]["total_count"] == 1

    r2 = client.get("/api/v2/strategies/backtest/results", params={"limit": 0})
    assert r2.status_code == 200
    assert r2.json()["data"]["total_count"] == 2


def test_backtest_results_error(client):
    type(client._deps["bt"]).backtest_results = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("res"))
    )
    r = client.get("/api/v2/strategies/backtest/results")
    assert r.status_code == 500


def test_ml_status_single_and_all(client):
    r = client.get("/api/v2/strategies/ml/status", params={"symbol": "BTCUSDT"})
    assert r.status_code == 200
    assert r.json()["data"]["symbol"] == "BTCUSDT"

    r2 = client.get("/api/v2/strategies/ml/status")
    assert r2.status_code == 200
    assert "ETHUSDT" in r2.json()["data"]


def test_ml_status_error(client):
    client._deps["ml"].get_model_status.side_effect = RuntimeError("ml")
    assert client.get("/api/v2/strategies/ml/status").status_code == 500


def test_ml_train_enqueues(client):
    r = client.post(
        "/api/v2/strategies/ml/train",
        params={
            "symbol": "BTCUSDT",
            "start_date": "2026-01-01T00:00:00",
            "end_date": "2026-01-02T00:00:00",
            "model_type": "LSTM",
        },
    )
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert r.json()["data"]["data_points"] > 0


def test_ml_train_error(client, monkeypatch):
    import pandas as pd

    monkeypatch.setattr(
        pd, "date_range", MagicMock(side_effect=RuntimeError("dates"))
    )
    r = client.post(
        "/api/v2/strategies/ml/train",
        params={
            "symbol": "BTCUSDT",
            "start_date": "2026-01-01T00:00:00",
            "end_date": "2026-01-02T00:00:00",
        },
    )
    assert r.status_code == 500


def test_get_ml_engine_import_error(monkeypatch, paper_env):
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "app.services.hybrid_ml_engine" or name.endswith(
            "hybrid_ml_engine"
        ):
            raise ImportError("no tensorflow")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    with pytest.raises(HTTPException) as ei:
        sr.get_ml_engine()
    assert ei.value.status_code == 503


@pytest.mark.asyncio
async def test_background_tasks(deps, monkeypatch):
    await sr.execute_strategy_task(
        "BTCUSDT", _strategy_spec(), AccountState(**_account_payload())
    )

    # success path with DeepModelConfig stubbed via fake engine
    await sr.train_model_task(deps["ml"], MagicMock(), "BTCUSDT", "LSTM")

    # error path
    deps["ml"].train_deep_model = AsyncMock(side_effect=RuntimeError("train"))
    await sr.train_model_task(deps["ml"], MagicMock(), "BTCUSDT", "LSTM")


def test_factory_helpers_construct(paper_env):
    from app.core.risk_manager import RiskManager
    from app.services.backtesting_service import BacktestingService
    from app.services.strategy_selector import StrategySelector

    rm = sr.get_risk_manager()
    assert isinstance(rm, RiskManager)
    assert isinstance(sr.get_strategy_selector(rm), StrategySelector)
    assert isinstance(sr.get_backtesting_service(), BacktestingService)
