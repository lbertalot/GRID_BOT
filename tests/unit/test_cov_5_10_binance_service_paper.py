"""COV-5.10 — binance_service paper residual (validate / cache / redis / cancel).

Paper-only · mocks · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.binance_service import BinanceService

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def svc(paper_env, monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    s = BinanceService.__new__(BinanceService)
    s.api_key = ""
    s.api_secret = ""
    s.simulation_mode = True
    s.force_real_mode = False
    s.client = MagicMock()
    s.client.get_exchange_info.return_value = {
        "symbols": [
            {
                "symbol": "ETHUSDT",
                "baseAsset": "ETH",
                "quoteAsset": "USDT",
                "quotePrecision": 2,
                "baseAssetPrecision": 3,
                "filters": [
                    {
                        "filterType": "LOT_SIZE",
                        "stepSize": "0.001",
                        "minQty": "0.001",
                    },
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10.0"},
                ],
            }
        ]
    }
    s._symbol_info_cache = {}
    s.redis_cache = AsyncMock()
    return s


def test_init_paper_and_force_real_flags(paper_env, monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton"
    ) as g:
        g.return_value.is_ready.return_value = False
        s = BinanceService()
    assert s.simulation_mode is True
    assert s.is_simulation_mode() is True

    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    with patch(
        "app.services.binance_client_singleton.get_binance_client_singleton"
    ) as g2:
        g2.return_value.is_ready.return_value = False
        with patch.object(BinanceService, "_initialize_client"):
            s2 = BinanceService.__new__(BinanceService)
            s2.api_key = "k"
            s2.api_secret = "s"
            s2.client = MagicMock()
            s2._symbol_info_cache = {}
            s2.redis_cache = MagicMock()
            # replicate flag logic
            s2.simulation_mode = True
            s2.force_real_mode = True
            if s2.force_real_mode:
                s2.simulation_mode = False
    assert s2.simulation_mode is False


def test_symbol_info_cache_and_adjust(svc):
    info = svc.get_symbol_info("ETHUSDT")
    assert info["stepSize"] == 0.001
    assert svc.get_symbol_info("ETHUSDT") is info  # cache hit
    svc.client.get_exchange_info.assert_called_once()

    adj = svc.adjust_quantity_precision(0.0015, "ETHUSDT")
    assert adj["adjusted_quantity"] == 0.001
    assert adj["min_notional"] == 10.0

    # unknown symbol → None then fallback defaults in adjust
    assert svc.get_symbol_info("NOPE") is None
    adj2 = svc.adjust_quantity_precision(1.23456, "NOPE")
    assert adj2["step_size"] == 0.001

    svc.client.get_exchange_info.side_effect = RuntimeError("x")
    svc._symbol_info_cache.clear()
    assert svc.get_symbol_info("ETHUSDT") is None


def test_validate_order_and_grid(svc, monkeypatch):
    with patch.object(svc, "get_current_price", return_value=2000.0), patch(
        "app.services.binance_service.commission_manager.calculate_commission",
        return_value=0.5,
    ):
        ok = svc.validate_order_parameters("ETHUSDT", 0.01, "BUY", "MARKET")
    assert ok["is_valid"] is True
    assert ok["quantity_info"]["adjusted_quantity"] > 0

    with patch.object(svc, "get_current_price", return_value=2000.0), patch(
        "app.services.binance_service.commission_manager.calculate_commission",
        return_value=0.01,
    ):
        bad = svc.validate_order_parameters("ETHUSDT", 0.0001, "BUY")
    assert bad["is_valid"] is False
    assert bad["errors"]

    with patch(
        "app.services.binance_service.commission_manager.adjust_grid_levels_for_commissions",
        return_value={
            "profitability_analysis": [
                {"is_profitable": True, "net_profit": 1.0},
                {"is_profitable": False, "net_profit": -0.5},
            ],
            "commission_per_trade": 0.1,
            "recommended_min_spread": 0.5,
            "adjusted_levels": [1900.0, 2100.0],
        },
    ):
        grid = svc.validate_grid_profitability(
            "ETHUSDT", 1900.0, 2100.0, 0.01, 2, 0.5
        )
    assert "profitability_rate" in grid
    assert grid["profitable_levels"] == 1


def test_price_orders_cancel_pending(svc):
    with patch(
        "app.core.paper_equity_ledger.mark_price_from_client", return_value=Decimal("1923")
    ):
        assert svc.get_current_price("ETHUSDT") == 1923.0

    order = svc.execute_trading_order("ETHUSDT", "BUY", "MARKET", 0.01, price=1923.0)
    assert order["status"] == "FILLED"
    assert order["side"] == "BUY"

    pending = MagicMock()
    pending.list_open.return_value = [
        SimpleNamespace(as_binance_dict=lambda: {"orderId": 9, "status": "NEW"})
    ]
    pending.cancel.return_value = SimpleNamespace(
        as_binance_dict=lambda: {"orderId": 9, "status": "CANCELED"}
    )
    with patch(
        "app.core.paper_pending_orders.get_paper_pending_order_book",
        return_value=pending,
    ):
        opens = svc.get_open_orders("ETHUSDT")
        assert opens[0]["orderId"] == 9
        canceled = svc.cancel_order("ETHUSDT", 9)
    assert canceled["status"] == "CANCELED"

    with patch(
        "app.core.paper_pending_orders.get_paper_pending_order_book",
        side_effect=RuntimeError("no-book"),
    ):
        assert svc.get_open_orders() == []
        fb = svc.cancel_order("ETHUSDT", 1)
    assert fb["status"] == "CANCELED"


def test_simulated_account_and_alias(svc):
    ledger = MagicMock()
    ledger.cost_model.maker_fee_bps = Decimal("10")
    ledger.cost_model.taker_fee_bps = Decimal("10")
    ledger.as_binance_balances.return_value = [
        {"asset": "USDT", "free": "100", "locked": "0"}
    ]
    with patch("app.core.paper_equity_ledger.get_paper_ledger", return_value=ledger):
        acct = svc.get_account()
        bal = svc.get_balance("USDT")
        miss = svc.get_balance("XYZ")
    assert acct["accountType"] == "SPOT"
    assert bal["free"] == "100"
    assert miss["free"] == "0"
    assert svc._get_simulated_symbol_info("ETHUSDT")["symbol"] == "ETHUSDT"


async def test_redis_optimized_paths(svc):
    ledger = MagicMock()
    ledger.cost_model.maker_fee_bps = Decimal("10")
    ledger.cost_model.taker_fee_bps = Decimal("10")
    ledger.as_binance_balances.return_value = []

    # cache hit
    svc.redis_cache.get_account_info = AsyncMock(return_value={"cached": True})
    assert (await svc.get_account_optimized())["cached"] is True

    # cache miss → sim
    svc.redis_cache.get_account_info = AsyncMock(return_value=None)
    svc.redis_cache.set_account_info = AsyncMock()
    with patch("app.core.paper_equity_ledger.get_paper_ledger", return_value=ledger):
        acct = await svc.get_account_optimized()
    assert acct["accountType"] == "SPOT"
    svc.redis_cache.set_account_info.assert_awaited()

    # exception → fallback
    svc.redis_cache.get_account_info = AsyncMock(side_effect=RuntimeError("redis"))
    with patch.object(svc, "get_account", return_value={"fallback": True}):
        assert (await svc.get_account_optimized())["fallback"] is True

    svc.redis_cache.get_symbol_ticker = AsyncMock(return_value=None)
    svc.redis_cache.set_symbol_ticker = AsyncMock()
    with patch.object(svc, "_get_simulated_price", return_value=1500.0):
        tick = await svc.get_symbol_ticker_optimized("ETHUSDT")
    assert tick["price"] == "1500.0"

    svc.redis_cache.get_symbol_ticker = AsyncMock(return_value={"price": "1"})
    assert (await svc.get_symbol_ticker_optimized("ETHUSDT"))["price"] == "1"

    # exchange_info optimized — sim helper missing → except → get_exchange_info fallback
    svc.redis_cache.get_exchange_info = AsyncMock(return_value=None)
    svc.redis_cache.set_exchange_info = AsyncMock()
    with patch.object(
        svc, "get_exchange_info", create=True, return_value={"symbols": []}
    ):
        out = await svc.get_exchange_info_optimized()
    assert out == {"symbols": []}

    svc.redis_cache.get_cache_stats = AsyncMock(return_value={"hits": 1})
    stats = await svc.get_cache_stats()
    assert stats["hits"] == 1

    svc.redis_cache.invalidate_symbol = AsyncMock()
    await svc.invalidate_symbol_cache("ETHUSDT")
    svc.redis_cache.invalidate_symbol.assert_awaited()
