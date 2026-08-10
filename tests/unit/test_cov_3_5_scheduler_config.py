"""COV-3.5 — config_manager / optimized_scheduler / grid_job (mocks).

Paper-only · no live · PROMOTE_LIVE: NO.
Hooks de schedule sin disparar órdenes reales ni cron en proceso de test.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scheduler import grid_job as gj
from app.services.config_manager import (
    ConfigManager,
    MarketData,
    OptimizationRequest,
    OptimizationStrategy,
)

pytestmark = pytest.mark.usefixtures("paper_env")


# ── grid_job (mayor gap) ─────────────────────────────────────────────────────


def test_adjust_quantity_precision_and_config_helpers():
    assert gj.adjust_quantity_precision(0.0074, "BNBUSDT") == 0.007
    assert gj.adjust_quantity_precision(0.0000001, "BNBUSDT") == 0.001  # floor→min
    assert gj.adjust_quantity_precision(1.55, "GUNUSDT") == 1.0
    assert gj.adjust_quantity_precision(0.123456, "UNKNOWNUSDT") == 0.123

    original = dict(gj.multi_asset_grid_config)
    try:
        gj.update_grid_config({"BNBUSDT": {**original["BNBUSDT"], "quantity": 0.009}})
        assert gj.get_grid_config()["BNBUSDT"]["quantity"] == 0.009
    finally:
        gj.multi_asset_grid_config.clear()
        gj.multi_asset_grid_config.update(original)


def test_execute_grid_trading_job_mocked_no_live(monkeypatch):
    """No Client real, no OrderValidator live, no telegram real."""
    cfg = {
        "BNBUSDT": {
            "symbol": "BNBUSDT",
            "min_price": 700.0,
            "max_price": 800.0,
            "grids": 4,
            "quantity": 0.01,
            "last_action": None,
            "is_active": True,
        },
        "IDLEUSDT": {
            "symbol": "IDLEUSDT",
            "min_price": 1.0,
            "max_price": 2.0,
            "grids": 4,
            "quantity": 1.0,
            "last_action": None,
            "is_active": False,
        },
        "LOWUSDT": {
            "symbol": "LOWUSDT",
            "min_price": 1.0,
            "max_price": 2.0,
            "grids": 4,
            "quantity": 10.0,
            "last_action": None,
            "is_active": True,
        },
        "SELLUSDT": {
            "symbol": "SELLUSDT",
            "min_price": 1.0,
            "max_price": 2.0,
            "grids": 4,
            "quantity": 5.0,
            "last_action": None,
            "is_active": True,
        },
        "ERRUSDT": {
            "symbol": "ERRUSDT",
            "min_price": 1.0,
            "max_price": 2.0,
            "grids": 4,
            "quantity": 1.0,
            "last_action": None,
            "is_active": True,
        },
        "NOFILLUSDT": {
            "symbol": "NOFILLUSDT",
            "min_price": 1.0,
            "max_price": 2.0,
            "grids": 4,
            "quantity": 1.0,
            "last_action": None,
            "is_active": True,
        },
        "FAILUSDT": {
            "symbol": "FAILUSDT",
            "min_price": 1.0,
            "max_price": 2.0,
            "grids": 4,
            "quantity": 1.0,
            "last_action": None,
            "is_active": True,
        },
    }
    monkeypatch.setattr(gj, "multi_asset_grid_config", cfg)

    client = MagicMock()
    last_symbol = {"s": None}

    def _ticker(symbol):
        last_symbol["s"] = symbol
        if symbol == "ERRUSDT":
            raise RuntimeError("ticker boom")
        prices = {
            "BNBUSDT": "750",
            "LOWUSDT": "1.5",
            "SELLUSDT": "1.5",
            "NOFILLUSDT": "1.5",
            "FAILUSDT": "1.5",
        }
        return {"price": prices.get(symbol, "1")}

    client.get_symbol_ticker.side_effect = _ticker

    by_sym = {
        "BNBUSDT": {"action": "BUY", "price": 750.0},
        "LOWUSDT": {"action": "BUY", "price": 1.5},
        "SELLUSDT": {"action": "SELL", "price": 1.5},
        "NOFILLUSDT": {"action": "BUY", "price": 1.5},
        "FAILUSDT": {"action": "BUY", "price": 1.5},
    }

    def _decide(price, levels, last):
        return by_sym.get(last_symbol["s"], {"action": None})

    def _place(symbol, side, qty):
        if symbol == "FAILUSDT":
            return {"success": False, "error": "rejected"}
        if symbol == "NOFILLUSDT":
            return {
                "success": True,
                "order": {"orderId": 99, "fills": []},
            }
        return {
            "success": True,
            "order": {
                "orderId": 42,
                "fills": [{"price": "750.0", "qty": str(qty)}],
            },
        }

    validator = MagicMock()
    validator.place_market_order_with_validation.side_effect = _place

    with patch.object(gj, "Client", return_value=client), patch.object(
        gj, "OrderValidator", return_value=validator
    ), patch.object(
        gj, "calculate_grid_levels", return_value=[700, 733, 766, 800]
    ), patch.object(gj, "decide_grid_action", side_effect=_decide), patch.object(
        gj, "send_telegram_alert"
    ) as tg, patch.object(
        gj, "adjust_quantity_precision", side_effect=lambda q, s: q
    ):
        client.get_account.return_value = {
            "balances": [
                {"asset": "USDT", "free": "5"},
                {"asset": "BNB", "free": "0"},
                {"asset": "SELL", "free": "0.1"},
                {"asset": "NOFILL", "free": "10"},
                {"asset": "FAIL", "free": "10"},
                {"asset": "LOW", "free": "0"},
            ]
        }
        gj.execute_grid_trading_job()

        client.get_account.return_value = {
            "balances": [
                {"asset": "USDT", "free": "100000"},
                {"asset": "NOFILL", "free": "100"},
                {"asset": "FAIL", "free": "100"},
                {"asset": "BNB", "free": "10"},
                {"asset": "SELL", "free": "0.1"},
            ]
        }
        for k in list(cfg):
            cfg[k]["is_active"] = k in (
                "NOFILLUSDT",
                "FAILUSDT",
                "BNBUSDT",
                "SELLUSDT",
            )
        gj.execute_grid_trading_job()

    assert tg.call_count >= 1
    assert cfg["BNBUSDT"]["last_action"] == "BUY"
    assert validator.place_market_order_with_validation.called
    assert client.create_order.call_count == 0


def test_execute_grid_job_outer_error_and_start_scheduler_mocked(monkeypatch):
    # Client() está fuera del try interno; get_account en el try externo.
    client = MagicMock()
    client.get_account.side_effect = RuntimeError("account down")
    with patch.object(gj, "Client", return_value=client), patch.object(
        gj, "OrderValidator", return_value=MagicMock()
    ):
        gj.execute_grid_trading_job()

    fake_sched = MagicMock()
    monkeypatch.setattr(gj, "scheduler", None)
    with patch.object(gj, "BackgroundScheduler", return_value=fake_sched):
        gj.start_scheduler()
        fake_sched.add_job.assert_called_once()
        fake_sched.start.assert_called_once()
        gj.start_scheduler()
        assert fake_sched.start.call_count == 1
    monkeypatch.setattr(gj, "scheduler", None)


# ── config_manager residual gaps ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_config_manager_unsupported_and_error_branches():
    mgr = ConfigManager()
    md = MarketData(
        symbol="BTC",
        current_price=100.0,
        volatility=0.05,
        volume_24h=1e6,
        price_change_24h=1.0,
        high_24h=110,
        low_24h=90,
        timestamp=datetime.now(),
    )

    with patch.object(
        mgr, "_get_market_data", new_callable=AsyncMock, return_value=md
    ):
        req = OptimizationRequest(symbol="BTC", investment_amount=100.0)
        object.__setattr__(req, "strategy", "not_a_strategy")
        with pytest.raises(ValueError, match="no soportada"):
            await mgr.optimize_parameters(req)

    with patch.object(
        mgr, "_get_market_data", new_callable=AsyncMock, return_value=md
    ), patch.object(
        mgr,
        "_optimize_grid_strategy",
        new_callable=AsyncMock,
        side_effect=RuntimeError("x"),
    ):
        with pytest.raises(RuntimeError):
            await mgr.optimize_parameters(
                OptimizationRequest(symbol="BTC", investment_amount=50.0)
            )

    # except+raise en helpers: forzar ZeroDivision vía current_price=0
    md0 = MarketData(
        symbol="BTC",
        current_price=0.0,
        volatility=0.2,
        volume_24h=2e6,
        price_change_24h=0.0,
        high_24h=1,
        low_24h=0,
        timestamp=datetime.now(),
    )
    with pytest.raises(ZeroDivisionError):
        await mgr._optimize_volatility_based(
            OptimizationRequest(symbol="BTC", investment_amount=50.0), md0
        )
    with pytest.raises(ZeroDivisionError):
        await mgr._optimize_volume_based(
            OptimizationRequest(symbol="BTC", investment_amount=50.0), md0
        )
    with patch.object(
        mgr, "_get_historical_data", new_callable=AsyncMock, side_effect=RuntimeError("h")
    ):
        with pytest.raises(RuntimeError):
            await mgr._optimize_ml_based(
                OptimizationRequest(
                    symbol="BTC",
                    strategy=OptimizationStrategy.MACHINE_LEARNING,
                    investment_amount=50.0,
                ),
                md,
            )


# ── optimized_scheduler residual ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_start_reinit_and_uptime():
    from app.scheduler.optimized_scheduler import OptimizedGridScheduler

    s = OptimizedGridScheduler()
    s.scheduler = MagicMock()
    s.grid_manager = None
    with patch.object(s, "initialize", new_callable=AsyncMock, return_value=True), patch(
        "app.scheduler.optimized_scheduler.send_telegram_alert"
    ):
        s.grid_manager = MagicMock(config=SimpleNamespace(assets={}))
        # start when grid_manager was None → initialize
        s2 = OptimizedGridScheduler()
        s2.scheduler = MagicMock()
        s2.grid_manager = None
        with patch.object(
            s2, "initialize", new_callable=AsyncMock
        ) as init, patch(
            "app.scheduler.optimized_scheduler.send_telegram_alert"
        ):
            async def _init():
                s2.grid_manager = MagicMock(config=SimpleNamespace(assets={"A": {}}))
                return True

            init.side_effect = _init
            assert await s2.start() is True
            init.assert_called()

    assert s._calculate_uptime() == "Unknown"
    s.last_cycle_time = datetime.now()
    assert isinstance(s._calculate_uptime(), str)
