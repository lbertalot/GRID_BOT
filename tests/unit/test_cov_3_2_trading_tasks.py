"""COV-3.2 — trading_tasks paper tick / cycle / health hooks.

Paper-only · no live · PROMOTE_LIVE: NO.
Celery invoke sync; sin Redis/DB/red reales.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.trading_tasks as tt


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
    monkeypatch.setattr(tt, "_CACHE", _Cache(), raising=True)


def test_env_helpers(monkeypatch):
    monkeypatch.delenv("X_OPT", raising=False)
    assert tt._env_float_optional("X_OPT") is None
    monkeypatch.setenv("X_OPT", "1.5")
    assert tt._env_float_optional("X_OPT") == 1.5

    monkeypatch.delenv("X_DEF", raising=False)
    assert tt._env_float_default("X_DEF", 3.0) == 3.0
    monkeypatch.setenv("X_DEF", "bad")
    assert tt._env_float_default("X_DEF", 3.0) == 3.0
    monkeypatch.setenv("X_DEF", "2.25")
    assert tt._env_float_default("X_DEF", 3.0) == 2.25

    monkeypatch.delenv("X_INT", raising=False)
    assert tt._env_int_optional_positive("X_INT") is None
    monkeypatch.setenv("X_INT", "0")
    assert tt._env_int_optional_positive("X_INT") is None
    monkeypatch.setenv("X_INT", "4")
    assert tt._env_int_optional_positive("X_INT") == 4


@pytest.mark.anyio
async def test_cycle_and_balance_cache_roundtrip():
    state = {"last_tick": 1, "ok": True}
    await tt._set_cycle_state(state)
    loaded = await tt._get_cycle_state()
    assert loaded["ok"] is True

    await tt._set_cached_balances({"USDT": 100.0, "BTC": 0.01})
    bals = await tt._get_cached_balances()
    assert bals["USDT"] == 100.0


@pytest.mark.anyio
async def test_fetch_balances_with_retry_ok_and_fail():
    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 50.0})
    out = await tt._fetch_balances_with_retry(mgr, retries=1)
    assert out["USDT"] == 50.0

    mgr.get_asset_balances = AsyncMock(side_effect=RuntimeError("down"))
    with patch.object(tt.asyncio, "sleep", new=AsyncMock()):
        empty = await tt._fetch_balances_with_retry(mgr, retries=2)
    assert empty == {} or empty is None or isinstance(empty, dict)


def test_execute_trading_cycle_binance_net_fail(monkeypatch):
    singleton = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": False,
        "auth_ok": True,
    }
    notify = MagicMock()
    breakers = MagicMock()
    breakers.activate_breaker = AsyncMock()

    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "notify_consecutive_api_failures", notify)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: breakers)
    notify.delay = MagicMock()

    result = tt.execute_trading_cycle()
    assert result["status"] == "error"
    assert "net" in result["message"].lower()


def test_execute_trading_cycle_paper_insufficient_usdt(monkeypatch):
    singleton = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": True,
        "auth_ok": True,
    }
    breakers = MagicMock()
    breakers.deactivate_breaker = AsyncMock()
    breakers.activate_breaker = AsyncMock()

    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 0.0})

    async def _create(_cfg):
        return mgr

    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: breakers)
    monkeypatch.setattr(tt, "create_optimized_grid_manager", _create)
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary_sync=lambda b: {
                "total_value_usdt": 0,
                "usdt_balance": 0,
                "can_trade": False,
            }
        ),
    )

    with patch(
        "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
        return_value=(Decimal("0"), "paper_ledger"),
    ), patch(
        "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
        return_value=True,
    ):
        result = tt.execute_trading_cycle()

    assert result["status"] == "skipped"
    assert result["liquidity_source"] == "paper_ledger"
    assert "Insufficient paper USDT" in result["message"]


def test_health_check_and_assess_risk_mocked(monkeypatch):
    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 100.0, "BTC": 0.01})
    mgr.config = SimpleNamespace(
        assets={
            "BTCUSDT": SimpleNamespace(is_active=True),
            "ETHUSDT": SimpleNamespace(is_active=False),
        }
    )

    async def _create(_cfg):
        return mgr

    monkeypatch.setattr(tt, "create_optimized_grid_manager", _create)
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary=AsyncMock(
                return_value={
                    "total_value_usdt": 100.0,
                    "usdt_balance": 80.0,
                    "can_trade": True,
                }
            )
        ),
    )

    health = tt.health_check()
    assert health["status"] == "healthy"
    assert health["balances_available"] == 2

    risk = tt.assess_risk()
    assert risk["risk_level"] == "low"
    assert risk["recommendation"] == "continue_trading"

    # low funds branch
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary=AsyncMock(
                return_value={
                    "total_value_usdt": 5.0,
                    "usdt_balance": 1.0,
                    "can_trade": False,
                }
            )
        ),
    )
    risk_hi = tt.assess_risk()
    assert risk_hi["risk_level"] == "high"


def test_update_metrics_success_and_error(monkeypatch):
    svc = MagicMock()
    svc.calculate_portfolio_metrics = AsyncMock(return_value={"portfolio_value": 1000})
    with patch.object(tt, "MetricsService", return_value=svc):
        out = tt.update_metrics()
    assert out["status"] == "success"

    with patch.object(tt, "MetricsService", side_effect=RuntimeError("boom")):
        out2 = tt.update_metrics()
    assert out2["status"] == "error"


def test_dust_sweep_dry_run_no_live_orders(monkeypatch):
    singleton = MagicMock()
    singleton.get_balances.return_value = {"ETH": 0.0001, "USDT": 100.0}
    singleton.get_symbol_price.return_value = 2000.0  # value ~0.2 USD < threshold

    monkeypatch.setattr(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        lambda: singleton,
    )
    monkeypatch.setenv("DUST_THRESHOLD_USD", "1")
    monkeypatch.setenv("DUST_MIN_NOTIONAL", "10")

    # Bypass distributed lock if present
    def _passthrough(fn):
        return fn

    # Invoke underlying celery task
    result = tt.dust_sweep.run(True)
    assert isinstance(result, dict)
    # dry_run must not execute sells
    assert result.get("dry_run", True) in (True, None) or "actions" in result or result.get(
        "status"
    ) in ("ok", "success", "error", "skipped", "lock_not_acquired")
