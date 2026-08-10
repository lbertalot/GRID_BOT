"""COV-5.5 — trading_tasks residual: calibration + rebalancer V2 + assess/metrics/health.

Paper-only · mocks · PROMOTE_LIVE: NO.
Path rebalancer = exchange SoT (`should_skip_exchange_rebalancer=False`); sin red real.
"""

from __future__ import annotations

import json
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
    monkeypatch.setattr(tt, "CALIBRATION_MODE", False, raising=False)
    monkeypatch.setattr(tt, "_CACHE", _Cache(), raising=True)
    monkeypatch.setattr(
        "app.core.distributed_lock.get_redis_client",
        MagicMock(side_effect=RedisError("cov-5.5-no-redis")),
    )


def _run_cycle():
    return tt.execute_trading_cycle.__wrapped__()


def _auth_ok(monkeypatch, *, balances=None, usdt_summary=5.0):
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
    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(
        return_value=balances or {"USDT": float(usdt_summary), "ETH": 0.01}
    )
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
                "usdt_balance": usdt_summary,
                "total_value_usdt": usdt_summary,
                "can_trade": True,
            },
            get_trading_summary=AsyncMock(
                return_value={
                    "usdt_balance": usdt_summary,
                    "total_value_usdt": usdt_summary,
                    "can_trade": True,
                }
            ),
        ),
    )
    return mgr, breakers


def test_execute_calibration_mode_with_and_without_balance(monkeypatch):
    monkeypatch.setattr(tt, "CALIBRATION_MODE", True, raising=False)
    _auth_ok(monkeypatch, usdt_summary=50.0)

    with patch(
        "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
        return_value=(Decimal("50"), "paper_ledger"),
    ), patch(
        "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
        return_value=True,
    ):
        hi = _run_cycle()
    assert hi["status"] == "calibration", hi

    _auth_ok(monkeypatch, usdt_summary=5.0)
    with patch(
        "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
        return_value=(Decimal("5"), "paper_ledger"),
    ), patch(
        "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
        return_value=True,
    ):
        lo = _run_cycle()
    assert lo["status"] == "calibration", lo


def test_rebalancer_success_still_short_skips(monkeypatch):
    mgr, _ = _auth_ok(monkeypatch, usdt_summary=5.0)
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 8.0})
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary_sync=lambda b: {
                "usdt_balance": 5.0,
                "can_trade": False,
            },
            get_trading_summary=AsyncMock(
                return_value={"usdt_balance": 8.0, "can_trade": False}
            ),
        ),
    )
    rebal = MagicMock()
    rebal.check_and_rebalance = AsyncMock(return_value={"status": "success"})
    monkeypatch.setattr(tt, "auto_rebalancer_v2", rebal)

    with patch(
        "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
        return_value=(Decimal("5"), "exchange"),
    ), patch(
        "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
        return_value=False,
    ):
        out = _run_cycle()

    assert out["status"] == "skipped"
    assert "after rebalancing" in out["message"].lower()


def test_rebalancer_success_restored_hits_fallback_skip(monkeypatch):
    """Tras liquidez restaurada el código aún cae en return Insufficient USDT (L1081)."""
    mgr, _ = _auth_ok(monkeypatch, usdt_summary=5.0)
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 50.0})
    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary_sync=lambda b: {
                "usdt_balance": 5.0,
                "can_trade": False,
            },
            get_trading_summary=AsyncMock(
                return_value={"usdt_balance": 50.0, "can_trade": True}
            ),
        ),
    )
    rebal = MagicMock()
    rebal.check_and_rebalance = AsyncMock(return_value={"status": "success"})
    monkeypatch.setattr(tt, "auto_rebalancer_v2", rebal)

    with patch(
        "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
        return_value=(Decimal("5"), "exchange"),
    ), patch(
        "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
        return_value=False,
    ):
        out = _run_cycle()

    assert out["status"] == "skipped"
    assert out["message"] == "Insufficient USDT"
    rebal.check_and_rebalance.assert_awaited()


def test_rebalancer_non_success_detail_variants(monkeypatch):
    _auth_ok(monkeypatch, usdt_summary=5.0)
    rebal = MagicMock()
    monkeypatch.setattr(tt, "auto_rebalancer_v2", rebal)

    cases = [
        {"status": "blocked", "message": "breaker"},
        {"status": "skipped", "reason": "cooldown"},
        {"status": "error", "result": {"message": "nested-fail"}},
        {"status": "weird"},
    ]
    for payload in cases:
        rebal.check_and_rebalance = AsyncMock(return_value=payload)
        with patch(
            "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
            return_value=(Decimal("5"), "exchange"),
        ), patch(
            "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
            return_value=False,
        ):
            out = _run_cycle()
        assert out["status"] == "skipped"
        assert out["message"].startswith("Rebalancing:")


def test_rebalancer_raises_skips(monkeypatch):
    _auth_ok(monkeypatch, usdt_summary=5.0)
    rebal = MagicMock()
    rebal.check_and_rebalance = AsyncMock(side_effect=RuntimeError("rebal-boom"))
    monkeypatch.setattr(tt, "auto_rebalancer_v2", rebal)

    with patch(
        "app.core.paper_cycle_liquidity.resolve_available_usdt_for_cycle",
        return_value=(Decimal("5"), "exchange"),
    ), patch(
        "app.core.paper_cycle_liquidity.should_skip_exchange_rebalancer",
        return_value=False,
    ):
        out = _run_cycle()

    assert out["status"] == "skipped"
    assert "auto-rebalancing" in out["message"].lower()


def test_assess_risk_wrapped_levels(monkeypatch):
    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 20.0})
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=mgr)
    )

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
    low = tt.assess_risk.__wrapped__()
    assert low["risk_level"] == "low"

    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary=AsyncMock(
                return_value={
                    "total_value_usdt": 50.0,
                    "usdt_balance": 2.0,
                    "can_trade": False,
                }
            )
        ),
    )
    med = tt.assess_risk.__wrapped__()
    assert med["risk_level"] == "medium"
    assert med["recommendation"] == "low_liquidity"

    monkeypatch.setattr(
        tt,
        "fund_manager",
        SimpleNamespace(
            get_trading_summary=AsyncMock(
                return_value={
                    "total_value_usdt": 5.0,
                    "usdt_balance": 5.0,
                    "can_trade": False,
                }
            )
        ),
    )
    high = tt.assess_risk.__wrapped__()
    assert high["risk_level"] == "high"

    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=None)
    )
    unknown = tt.assess_risk.__wrapped__()
    assert unknown["risk_level"] == "unknown"


def test_update_metrics_and_health_wrapped(monkeypatch):
    metrics = MagicMock()
    metrics.calculate_portfolio_metrics = AsyncMock(return_value={})
    monkeypatch.setattr(tt, "MetricsService", lambda: metrics)
    ok = tt.update_metrics.__wrapped__()
    assert ok["status"] == "success"

    monkeypatch.setattr(
        tt, "MetricsService", MagicMock(side_effect=RuntimeError("down"))
    )
    bad = tt.update_metrics.__wrapped__()
    assert bad["status"] == "error"

    eth = SimpleNamespace(is_active=True)
    mgr = MagicMock()
    mgr.get_asset_balances = AsyncMock(return_value={"USDT": 10.0, "ETH": 0.01})
    mgr.config.assets = {"ETHUSDT": eth}
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=mgr)
    )
    health = tt.health_check.__wrapped__()
    assert health["status"] == "healthy"
    assert health["assets_configured"] == 1
