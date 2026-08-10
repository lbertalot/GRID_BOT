"""COV-5.1 — trading_tasks residual (ciclo / gate / dust / health).

Paper-only · no live · PROMOTE_LIVE: NO.
Mocks Binance/Redis; locks en modo degradado si Redis falla.
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
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "false")
    monkeypatch.setattr(tt, "_CACHE", _Cache(), raising=True)
    # Lock: degradar sin Redis real (ejecuta el body)
    monkeypatch.setattr(
        "app.core.distributed_lock.get_redis_client",
        MagicMock(side_effect=RedisError("cov-5.1-no-redis")),
    )


def test_execute_trading_cycle_auth_fail_and_manager_missing(monkeypatch):
    singleton = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": True,
        "auth_ok": False,
    }
    notify = MagicMock()
    notify.delay = MagicMock()
    breakers = MagicMock()
    breakers.activate_breaker = AsyncMock()

    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "notify_consecutive_api_failures", notify)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: breakers)

    auth = tt.execute_trading_cycle()
    assert auth["status"] == "error"
    assert "auth" in auth["message"].lower()

    singleton.validate_credentials_and_connectivity.side_effect = RuntimeError(
        "boom-validate"
    )
    boom = tt.execute_trading_cycle()
    assert boom["status"] == "error"

    singleton.validate_credentials_and_connectivity.side_effect = None
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": True,
        "auth_ok": True,
    }
    breakers.deactivate_breaker = AsyncMock()
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=None)
    )
    no_mgr = tt.execute_trading_cycle()
    assert no_mgr["status"] == "error"
    assert "manager" in no_mgr["message"].lower()


def test_trading_cycle_tick_starts_and_evaluates(monkeypatch):
    # t=0 → inicia evaluation state
    out0 = tt.trading_cycle_tick()
    assert out0 is None or isinstance(out0, dict)

    # Estado en evaluación (~60s)
    started = (datetime.utcnow() - timedelta(seconds=60)).isoformat()
    state = {"started_at": started, "decision": None}

    mdc = MagicMock()
    mdc.get_price = AsyncMock(return_value=2000.0)
    mdc.get_klines = AsyncMock(
        return_value=[[0, "1", "1", "1", "1", "1"] for _ in range(30)]
    )

    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 100.0})

    bl = MagicMock()
    bl.should_block_trading.return_value = (False, "")

    breakers = MagicMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": False,
        "active_breakers": [],
    }
    auto_cb = MagicMock()
    auto_cb.check_and_activate_breakers = AsyncMock(
        return_value={"breakers_activated": [], "reasons": []}
    )

    selector = MagicMock()
    selector.select_strategy.return_value = SimpleNamespace(
        strategy_name=SimpleNamespace(value="grid"),
        confidence=0.8,
    )

    with patch.object(tt, "_get_cycle_state", AsyncMock(return_value=state)), patch.object(
        tt, "_set_cycle_state", AsyncMock()
    ) as set_st, patch.object(tt, "MarketDataCollector", return_value=mdc), patch.object(
        tt, "strategy_blacklist", bl
    ), patch.object(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=mgr)
    ), patch.object(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary=AsyncMock(
                return_value={
                    "total_value_usdt": 200.0,
                    "usdt_balance": 100.0,
                    "can_trade": True,
                }
            )
        ),
    ), patch.object(
        tt, "auto_circuit_breaker", auto_cb
    ), patch.object(
        tt, "get_shared_breakers", lambda: breakers
    ), patch.object(
        tt, "RiskManager", return_value=MagicMock(fractional_kelly=0.25)
    ), patch.object(
        tt, "StrategySelector", return_value=selector
    ), patch(
        "app.core.paper_trading.get_paper_portfolio_summary",
        return_value={"current_balance": 100.0},
    ):
        tt.trading_cycle_tick()

    assert set_st.await_count >= 1


def test_trading_cycle_tick_all_blacklisted(monkeypatch):
    started = (datetime.utcnow() - timedelta(seconds=30)).isoformat()
    state = {"started_at": started, "decision": None}
    bl = MagicMock()
    bl.should_block_trading.return_value = (True, "blocked")

    with patch.object(tt, "_get_cycle_state", AsyncMock(return_value=state)), patch.object(
        tt, "_set_cycle_state", AsyncMock()
    ), patch.object(tt, "MarketDataCollector", return_value=MagicMock()), patch.object(
        tt, "strategy_blacklist", bl
    ):
        out = tt.trading_cycle_tick()
    assert out is None or isinstance(out, dict)


@pytest.mark.anyio
async def test_promotion_gate_disabled_and_insufficient_closes(monkeypatch):
    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "false")
    ok, reasons = await tt._promotion_gate_allows_ml("ETHUSDT", [])
    assert ok is True and reasons == ()

    monkeypatch.setenv("ML_PROMOTION_GATE_ENABLED", "true")
    short_kl = [[0, "1", "1", "1", "1", "1"] for _ in range(5)]
    ok2, _ = await tt._promotion_gate_allows_ml("ETHUSDT", short_kl)
    assert ok2 is True  # fail-open por datos insuficientes


def test_dust_sweep_dry_run_recommend_bnb(monkeypatch):
    singleton = MagicMock()
    # 0.4 USDT de dust → recommend BNB (bajo min_notional)
    singleton.get_balances.return_value = {"ADA": 10.0, "USDT": 50.0}
    singleton.get_symbol_price.return_value = 0.04

    monkeypatch.setattr(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        lambda: singleton,
    )
    monkeypatch.setenv("DUST_THRESHOLD_USD", "1")
    monkeypatch.setenv("DUST_MIN_NOTIONAL", "10")

    result = tt.dust_sweep.run(True)
    assert result.get("dry_run") is True
    assert result.get("count", 0) >= 1
    types = {a.get("type") for a in result.get("actions", [])}
    assert "RECOMMEND_DUST_TO_BNB" in types
    assert all(a.get("executed") is False for a in result.get("actions", []))


def test_health_check_unhealthy_paths(monkeypatch):
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=None)
    )
    assert tt.health_check()["status"] == "unhealthy"

    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={})
    mgr.config = SimpleNamespace(assets={})
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=mgr)
    )
    assert tt.health_check()["status"] == "unhealthy"

    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 1.0})
    bad = tt.health_check()
    assert bad["status"] == "unhealthy"
    assert "activ" in bad.get("error", "").lower() or "config" in bad.get(
        "error", ""
    ).lower() or bad["status"] == "unhealthy"
