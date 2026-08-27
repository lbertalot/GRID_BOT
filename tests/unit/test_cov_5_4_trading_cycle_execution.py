"""COV-5.4 — trading_cycle_tick fase ejecución (240–300s) + execute_trading_cycle paper.

Paper-only · lock degradado · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError

import app.services.trading_tasks as tt

pytestmark = [pytest.mark.usefixtures("paper_env")]


class _Cache:
    def __init__(self):
        self.store = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value, ttl_seconds: int = 0):
        self.store[key] = (
            json.dumps(value) if isinstance(value, dict) else str(value)
        )


@pytest.fixture(autouse=True)
def _paper_celery_env(paper_env, monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")
    monkeypatch.setenv("ML_ENABLED", "false")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("CALIBRATION_MODE", "false")
    monkeypatch.setattr(tt, "_CACHE", _Cache(), raising=True)
    monkeypatch.setattr(
        "app.core.distributed_lock.get_redis_client",
        MagicMock(side_effect=RedisError("cov-5.4-no-redis")),
    )


def _state(elapsed_s: float, decision=None):
    started = (datetime.utcnow() - timedelta(seconds=elapsed_s)).isoformat()
    return {"started_at": started, "decision": decision}


def _run_cycle():
    """Ejecuta el body real (no proxy Celery) para cobertura fiable."""
    return tt.execute_trading_cycle.__wrapped__()


def test_tick_execution_ready_enqueues_cycle(monkeypatch):
    decisions = {
        "ETHUSDT": {
            "strategy": "grid",
            "confidence": 0.9,
            "price": 2000.0,
            "ready": True,
            "regime": "range",
        }
    }
    state = _state(250, decisions)
    breakers = MagicMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": False,
        "active_breakers": [],
    }
    delay = MagicMock()

    with patch.object(tt, "_get_cycle_state", AsyncMock(return_value=state)), patch.object(
        tt, "_set_cycle_state", AsyncMock()
    ), patch.object(tt, "get_shared_breakers", lambda: breakers), patch.object(
        tt.execute_trading_cycle, "delay", delay
    ):
        out = tt.trading_cycle_tick()

    assert out["status"] == "ok"
    delay.assert_called_once()


def test_tick_execution_fallback_without_ready(monkeypatch):
    decisions = {
        "ETHUSDT": {
            "strategy": "grid",
            "confidence": 0.5,
            "price": 2000.0,
            "ready": False,
            "regime": "range",
        }
    }
    state = _state(250, decisions)
    breakers = MagicMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": False,
        "active_breakers": [],
    }
    delay = MagicMock()

    with patch.object(tt, "_get_cycle_state", AsyncMock(return_value=state)), patch.object(
        tt, "_set_cycle_state", AsyncMock()
    ), patch.object(tt, "get_shared_breakers", lambda: breakers), patch.object(
        tt.execute_trading_cycle, "delay", delay
    ):
        out = tt.trading_cycle_tick()

    assert out["status"] == "ok"
    delay.assert_called_once()


def test_tick_execution_skip_when_no_decisions(monkeypatch):
    state = _state(250, {})
    breakers = MagicMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": False,
        "active_breakers": [],
    }
    delay = MagicMock()

    with patch.object(tt, "_get_cycle_state", AsyncMock(return_value=state)), patch.object(
        tt, "_set_cycle_state", AsyncMock()
    ), patch.object(tt, "get_shared_breakers", lambda: breakers), patch.object(
        tt.execute_trading_cycle, "delay", delay
    ):
        out = tt.trading_cycle_tick()

    assert out["status"] == "ok"
    delay.assert_not_called()


def test_tick_execution_blocked_by_breakers(monkeypatch):
    decisions = {
        "ETHUSDT": {
            "strategy": "grid",
            "confidence": 0.9,
            "price": 2000.0,
            "ready": True,
            "regime": "range",
        }
    }
    state = _state(260, decisions)
    breakers = MagicMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": True,
        "active_breakers": ["system_integrity"],
    }
    delay = MagicMock()

    with patch.object(tt, "_get_cycle_state", AsyncMock(return_value=state)), patch.object(
        tt, "_set_cycle_state", AsyncMock()
    ), patch.object(tt, "get_shared_breakers", lambda: breakers), patch.object(
        tt.execute_trading_cycle, "delay", delay
    ):
        out = tt.trading_cycle_tick()

    assert out["status"] == "ok"
    delay.assert_not_called()


def test_tick_resets_cycle_after_five_minutes(monkeypatch):
    state = _state(310, {"ETHUSDT": {"ready": True}})
    set_st = AsyncMock()

    with patch.object(tt, "_get_cycle_state", AsyncMock(return_value=state)), patch.object(
        tt, "_set_cycle_state", set_st
    ), patch.object(tt.execute_trading_cycle, "delay", MagicMock()):
        out = tt.trading_cycle_tick()

    assert out["status"] == "ok"
    set_st.assert_awaited()
    new_state = set_st.await_args.args[0]
    assert new_state.get("decision") is None
    assert "started_at" in new_state


def test_execute_trading_cycle_paper_happy_mocked(monkeypatch):
    # El re-centrado está apagado por seguridad; este caso cubre la ruta opt-in.
    monkeypatch.setenv("ENABLE_DYNAMIC_GRID_RECENTER", "true")
    singleton = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": True,
        "auth_ok": True,
    }
    breakers = MagicMock()
    breakers.deactivate_breaker = AsyncMock()
    breakers.activate_breaker = AsyncMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": False,
        "active_breakers": [],
        "total_active": 0,
    }

    eth = SimpleNamespace(
        is_active=True, grids=3, min_price=0.0, max_price=0.0, grid_levels=[]
    )
    btc = SimpleNamespace(
        is_active=True, grids=3, min_price=0.0, max_price=0.0, grid_levels=[]
    )
    mgr = MagicMock()
    mgr.config.assets = {"ETHUSDT": eth, "BTCUSDT": btc}
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 200.0, "ETH": 0.1})
    mgr.execute_grid_trading_cycle = AsyncMock(
        return_value=[SimpleNamespace(symbol="ETHUSDT", status="success")]
    )

    wrapper = MagicMock()
    wrapper.get_price = AsyncMock(return_value=2000.0)
    metrics = MagicMock()
    metrics.calculate_portfolio_metrics = AsyncMock(return_value={})
    telegram = MagicMock()
    telegram.delay = MagicMock()

    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: breakers)
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=mgr)
    )
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary_sync=lambda b: {
                "total_value_usdt": 200,
                "usdt_balance": 150,
                "can_trade": True,
            }
        ),
    )
    monkeypatch.setattr(tt, "AsyncBinanceWrapper", lambda: wrapper)
    monkeypatch.setattr(tt, "MetricsService", lambda: metrics)
    monkeypatch.setattr(tt, "send_telegram_alert", telegram)

    with patch(
        "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
        return_value=(Decimal("150"), "paper_ledger"),
    ), patch(
        "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
        return_value=True,
    ):
        result = _run_cycle()

    assert result["status"] == "success"
    assert result["summary"]["mode"] == "PAPER"
    assert result["summary"]["trades_executed"] == 1
    assert eth.is_active is True
    assert btc.is_active is False
    assert eth.grid_levels
    telegram.delay.assert_called_once()
    metrics.calculate_portfolio_metrics.assert_awaited()


def test_execute_trading_cycle_skips_insufficient_paper_usdt(monkeypatch):
    singleton = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": True,
        "auth_ok": True,
    }
    breakers = MagicMock()
    breakers.deactivate_breaker = AsyncMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": False,
        "active_breakers": [],
    }
    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 1.0})

    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: breakers)
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=mgr)
    )
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary_sync=lambda b: {
                "usdt_balance": 1.0,
                "can_trade": False,
            }
        ),
    )

    with patch(
        "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
        return_value=(Decimal("5"), "paper_ledger"),
    ), patch(
        "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
        return_value=True,
    ):
        result = _run_cycle()

    assert result["status"] == "skipped"
    assert "paper" in result["message"].lower()


def test_execute_trading_cycle_skips_when_breakers_critical(monkeypatch):
    singleton = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": True,
        "auth_ok": True,
    }
    breakers = MagicMock()
    breakers.deactivate_breaker = AsyncMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": True,
        "active_breakers": ["system_integrity"],
    }
    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 200.0})

    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: breakers)
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=mgr)
    )
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary_sync=lambda b: {
                "usdt_balance": 150,
                "can_trade": True,
            }
        ),
    )

    with patch(
        "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
        return_value=(Decimal("150"), "paper_ledger"),
    ), patch(
        "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
        return_value=True,
    ):
        result = _run_cycle()

    assert result["status"] == "skipped"
    assert "breaker" in result["message"].lower()


def test_execute_trading_cycle_net_fail(monkeypatch):
    singleton = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": False,
        "auth_ok": True,
    }
    notify = MagicMock()
    notify.delay = MagicMock()
    breakers = MagicMock()
    breakers.activate_breaker = AsyncMock()

    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "notify_consecutive_api_failures", notify)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: breakers)

    result = _run_cycle()
    assert result["status"] == "error"
    assert "net" in result["message"].lower()
    notify.delay.assert_called()
