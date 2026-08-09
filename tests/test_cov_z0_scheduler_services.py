"""S-COV-85 Z0 — scheduler jobs + small services (mocked I/O). Paper-only."""

from __future__ import annotations

import asyncio
import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError

pytestmark = pytest.mark.usefixtures("paper_env")


# ── operation_tracking_job ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_operation_tracking_loop_ok_and_error():
    from app.scheduler import operation_tracking_job as mod

    tracker = MagicMock()
    tracker.force_operation_check = AsyncMock(
        side_effect=[None, RuntimeError("boom"), None]
    )
    sleeps = 0

    async def _sleep(_s):
        nonlocal sleeps
        sleeps += 1
        if sleeps >= 3:
            raise asyncio.CancelledError()

    with (
        patch.object(mod, "OperationTracker", return_value=tracker),
        patch.object(mod.asyncio, "sleep", _sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await mod.run_operation_tracking_forever(interval_seconds=0)

    assert tracker.force_operation_check.await_count == 3


# ── reconciliation_job ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reconciliation_forever_and_once(mock_binance):
    from app.scheduler import reconciliation_job as mod

    svc = MagicMock()
    svc.run_reconciliation_cycle = AsyncMock(
        side_effect=[{"ok": True}, RuntimeError("x"), {"ok": True}]
    )
    sleeps = 0

    async def _sleep(_s):
        nonlocal sleeps
        sleeps += 1
        if sleeps >= 3:
            raise asyncio.CancelledError()

    with (
        patch.object(mod, "get_binance_client_singleton", return_value=mock_binance),
        patch.object(mod, "get_shared_breakers", return_value=MagicMock()),
        patch.object(mod, "ReconciliationService", return_value=svc),
        patch.object(mod.asyncio, "sleep", _sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await mod.run_reconciliation_forever(interval_seconds=0)

    svc.run_reconciliation_cycle = AsyncMock(return_value={"reconciled": True})
    with (
        patch.object(mod, "get_binance_client_singleton", return_value=mock_binance),
        patch.object(mod, "get_shared_breakers", return_value=MagicMock()),
        patch.object(mod, "ReconciliationService", return_value=svc),
    ):
        out = await mod.run_reconciliation_once()
    assert out == {"reconciled": True}


# ── symbol_validator ────────────────────────────────────────────────────────


def test_symbol_validator():
    from app.services import symbol_validator as sv

    assert sv.is_valid_symbol("BTCUSDT") is True
    assert sv.is_valid_symbol("FAKEUSDT") is False
    assert sv.filter_invalid_symbols(["BTCUSDT", "ZZZ", "ETHUSDT"]) == [
        "BTCUSDT",
        "ETHUSDT",
    ]
    logger = MagicMock()
    assert sv.log_symbol_validation("OK", True, logger) is True
    logger.warning.assert_not_called()
    assert sv.log_symbol_validation("BAD", False, logger) is False
    logger.warning.assert_called_once()


# ── order_validation_dependency ─────────────────────────────────────────────


def test_get_order_validator(mock_binance):
    from app.services import order_validation_dependency as ovd

    with patch.object(
        ovd, "get_binance_client_singleton", return_value=mock_binance
    ):
        with patch.object(ovd, "OrderValidator") as OV:
            OV.return_value = MagicMock(name="validator")
            v = ovd.get_order_validator()
    OV.assert_called_once_with(mock_binance.client)
    assert v is OV.return_value


@pytest.mark.asyncio
async def test_validate_order_e2e_accept_and_reject():
    from app.services import order_validation_dependency as ovd

    validator = MagicMock()
    validator.validate_order_parameters.return_value = {
        "is_valid": True,
        "errors": [],
    }
    ok = await ovd.validate_order_e2e(
        "BTCUSDT", "BUY", "MARKET", 0.01, None, validator=validator
    )
    assert ok["is_valid"] is True

    validator.validate_order_parameters.return_value = {
        "is_valid": False,
        "errors": ["min_notional"],
    }
    with patch.object(ovd, "order_validation_rejects_total") as metric:
        metric.labels.return_value.inc = MagicMock()
        with pytest.raises(HTTPException) as ei:
            await ovd.validate_order_e2e(
                "BTCUSDT", "BUY", "LIMIT", 0.001, 1.0, validator=validator
            )
    assert ei.value.status_code == 400
    assert ei.value.detail["reason"] == "min_notional"

    # metrics raise → still HTTPException
    validator.validate_order_parameters.return_value = {
        "is_valid": False,
        "errors": [],
    }
    with patch.object(
        ovd,
        "order_validation_rejects_total",
        MagicMock(**{"labels.side_effect": RuntimeError("m")}),
    ):
        with pytest.raises(HTTPException) as ei2:
            await ovd.validate_order_e2e(
                "ETHUSDT", "SELL", "MARKET", 0.0, None, validator=validator
            )
    assert ei2.value.detail["reason"] == "invalid_order"


# ── ml_tasks ────────────────────────────────────────────────────────────────


def test_analyze_performance_ok_and_retry():
    from app.services import ml_tasks as mod

    out = mod.analyze_performance.run()
    assert out["sharpe_ratio"] == 0.0
    assert "volatility" in out

    with patch.object(mod.logger, "info", side_effect=RuntimeError("fail")):
        with pytest.raises(Exception):
            mod.analyze_performance.run()


# ── rebalancing_tasks ───────────────────────────────────────────────────────


def test_check_and_rebalance_skip_run_and_retry():
    from app.services import rebalancing_tasks as mod

    status_skip = {"assets_needing_rebalance": 0, "can_rebalance": True}
    status_go = {"assets_needing_rebalance": 2, "can_rebalance": True}
    rebalance_result = {"status": "rebalanced"}

    arb = MagicMock()
    arb.get_rebalance_status = AsyncMock(return_value=status_skip)
    arb.check_and_rebalance = AsyncMock(return_value=rebalance_result)

    with (
        patch(
            "app.core.distributed_lock.get_redis_client",
            side_effect=RedisError("offline"),
        ),
        patch("app.services.auto_rebalancer.auto_rebalancer", arb),
    ):
        skipped = mod.check_and_rebalance.run()
    assert skipped["status"] == "skipped"

    arb.get_rebalance_status = AsyncMock(return_value=status_go)
    with (
        patch(
            "app.core.distributed_lock.get_redis_client",
            side_effect=RedisError("offline"),
        ),
        patch("app.services.auto_rebalancer.auto_rebalancer", arb),
    ):
        ran = mod.check_and_rebalance.run()
    assert ran["status"] == "rebalanced"

    with (
        patch(
            "app.core.distributed_lock.get_redis_client",
            side_effect=RedisError("offline"),
        ),
        patch(
            "app.services.auto_rebalancer.auto_rebalancer",
            MagicMock(
                get_rebalance_status=AsyncMock(side_effect=RuntimeError("arb"))
            ),
        ),
    ):
        with pytest.raises(Exception):
            mod.check_and_rebalance.run()


# ── binance_client (deprecated thin wrapper) ────────────────────────────────


def test_binance_client_dummy_path(monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    mod_name = "app.services.binance_client"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    with pytest.warns(DeprecationWarning):
        mod = importlib.import_module(mod_name)
    assert mod.client.get_account() == {"balances": []}
    assert mod.client.get_symbol_ticker("BTCUSDT")["price"] == "0"
    assert mod.client.order_market_buy()["status"] == "FILLED"
    assert mod.client.order_market_sell()["status"] == "FILLED"


def test_binance_client_use_real_singleton_ready(monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "1")
    mod_name = "app.services.binance_client"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    singleton = MagicMock()
    singleton.is_ready.return_value = True
    singleton.client = MagicMock(name="real_client")

    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        return_value=singleton,
    ):
        with pytest.warns(DeprecationWarning):
            mod = importlib.import_module(mod_name)
    assert mod.client is singleton.client
    del sys.modules[mod_name]
    monkeypatch.setenv("USE_REAL_BINANCE", "0")


def test_binance_client_use_real_fallback_paths(monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "1")
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    monkeypatch.setenv("BINANCE_TESTNET", "false")
    mod_name = "app.services.binance_client"

    # singleton not ready → Client()
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    singleton = MagicMock()
    singleton.is_ready.return_value = False
    fake_client = MagicMock(name="constructed")
    with (
        patch(
            "app.services.binance_client_singleton.get_binance_client_singleton",
            return_value=singleton,
        ),
        patch("binance.client.Client", return_value=fake_client),
    ):
        with pytest.warns(DeprecationWarning):
            mod = importlib.import_module(mod_name)
    assert mod.client is fake_client

    # outer except → Client ok
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    with (
        patch(
            "app.services.binance_client_singleton.get_binance_client_singleton",
            side_effect=RuntimeError("no singleton"),
        ),
        patch("binance.client.Client", return_value=fake_client),
    ):
        with pytest.warns(DeprecationWarning):
            mod = importlib.import_module(mod_name)
    assert mod.client is fake_client

    # Client also fails → FallbackDummy
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    with (
        patch(
            "app.services.binance_client_singleton.get_binance_client_singleton",
            side_effect=RuntimeError("no singleton"),
        ),
        patch("binance.client.Client", side_effect=RuntimeError("no sdk")),
    ):
        with pytest.warns(DeprecationWarning):
            mod = importlib.import_module(mod_name)
    assert mod.client.get_account() == {"balances": []}
    assert mod.client.get_symbol_ticker("ETHUSDT")["symbol"] == "ETHUSDT"

    del sys.modules[mod_name]
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
