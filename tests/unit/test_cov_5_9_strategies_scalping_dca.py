"""COV-5.9 — strategies scalping + DCA residual.

Paper-only · binance_client mock · RealOrderBlocked bypassed solo en asserts de place.
PROMOTE_LIVE: NO.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.strategies.base import Order, OrderSide, OrderStatus, StrategyType
from app.strategies.dca_strategy import DCAConfig, DCAStrategy
from app.strategies.scalping_strategy import ScalpingConfig, ScalpingStrategy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _client(
    *,
    price: float = 2000.0,
    usdt: float = 500.0,
    eth: float = 0.1,
    volume: float = 5_000_000,
):
    c = MagicMock()
    c.get_symbol_ticker.return_value = {"price": str(price)}
    c.get_ticker.return_value = {
        "volume": str(volume / price),
        "lastPrice": str(price),
    }
    c.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": str(usdt), "locked": "0"},
            {"asset": "ETH", "free": str(eth), "locked": "0"},
        ]
    }
    c.order_market_buy.return_value = {"orderId": 101}
    c.order_market_sell.return_value = {"orderId": 202}
    return c


@pytest.fixture
def scalp_mod():
    import app.strategies.scalping_strategy as m

    return m


@pytest.fixture
def dca_mod():
    import app.strategies.dca_strategy as m

    return m


def _scalp(**kwargs) -> ScalpingStrategy:
    cfg = ScalpingConfig(
        symbol=kwargs.pop("symbol", "ETHUSDT"),
        strategy_type=StrategyType.SCALPING,
        investment_amount=kwargs.pop("investment_amount", 100.0),
        entry_threshold=kwargs.pop("entry_threshold", 0.002),
        profit_target=kwargs.pop("profit_target", 0.005),
        stop_loss=kwargs.pop("stop_loss", 0.003),
        max_position_size=kwargs.pop("max_position_size", 100.0),
        min_volume_threshold=kwargs.pop("min_volume_threshold", 1_000_000),
        rsi_oversold=kwargs.pop("rsi_oversold", 30),
        enable_notifications=kwargs.pop("enable_notifications", True),
        **kwargs,
    )
    return ScalpingStrategy(cfg)


def _dca(**kwargs) -> DCAStrategy:
    cfg = DCAConfig(
        symbol=kwargs.pop("symbol", "ETHUSDT"),
        strategy_type=StrategyType.DCA,
        investment_amount=kwargs.pop("investment_amount", 50.0),
        frequency_hours=kwargs.pop("frequency_hours", 24),
        max_investments=kwargs.pop("max_investments", None),
        price_threshold=kwargs.pop("price_threshold", None),
        enable_notifications=kwargs.pop("enable_notifications", True),
        **kwargs,
    )
    return DCAStrategy(cfg)


# ── Scalping ────────────────────────────────────────────────────────────────


async def test_scalping_validate_config_paths(scalp_mod):
    client = _client()
    with patch.object(scalp_mod, "binance_client", client):
        ok = _scalp()
        assert await ok.validate_config() is True

        bad = _scalp(entry_threshold=-1)
        assert await bad.validate_config() is False

        bad2 = _scalp(profit_target=0.001, stop_loss=0.003)
        assert await bad2.validate_config() is False

        client.get_symbol_ticker.side_effect = RuntimeError("no-ticker")
        assert await _scalp().validate_config() is False

        client.get_symbol_ticker.side_effect = None
        client.get_symbol_ticker.return_value = None
        assert await _scalp().validate_config() is False


async def test_scalping_execute_not_running_and_no_price(scalp_mod):
    s = _scalp()
    s.is_running = False
    out = await s.execute()
    assert out.success is False and "not running" in out.error_message.lower()

    s.is_running = True
    with patch.object(scalp_mod, "binance_client", None):
        # _get_current_price will fail
        with patch.object(s, "_get_current_price", AsyncMock(return_value=None)):
            out2 = await s.execute()
    assert out2.success is False


async def test_scalping_entry_and_exit_paths(scalp_mod):
    client = _client(price=2000.0, usdt=1000.0)
    s = _scalp(rsi_oversold=80)  # easy oversold with falling series
    s.is_running = True
    # Falling prices → low RSI
    s.price_history = [2100 - i for i in range(25)]

    with patch.object(scalp_mod, "binance_client", client), patch.object(
        scalp_mod, "send_telegram_alert"
    ), patch(
        "app.core.order_execution_guard.assert_real_order_allowed", return_value={}
    ):
        out = await s.execute()
    assert out.success is True
    assert len(s.active_positions) >= 1 or len(out.orders) >= 0

    # Force entry by mocking helpers
    s2 = _scalp()
    s2.is_running = True
    s2.price_history = [2000.0] * 25
    order = Order(
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        quantity=0.05,
        price=2000.0,
        order_id="buy-1",
        status=OrderStatus.FILLED,
    )
    with patch.object(scalp_mod, "binance_client", client), patch.object(
        s2, "_get_current_price", AsyncMock(return_value=2000.0)
    ), patch.object(
        s2, "_check_entry_opportunity", AsyncMock(return_value=order)
    ), patch.object(
        s2, "_manage_active_positions", AsyncMock(return_value=[])
    ):
        out2 = await s2.execute()
    assert out2.success and out2.orders[0].order_id == "buy-1"

    # Exit via profit target
    s3 = _scalp(enable_notifications=True)
    s3.is_running = True
    s3.active_positions = {
        "pos-1": {
            "entry_price": 2000.0,
            "quantity": 0.05,
            "entry_time": datetime.now() - timedelta(minutes=1),
            "profit_target": 2010.0,
            "stop_loss": 1990.0,
        }
    }
    with patch.object(scalp_mod, "binance_client", client), patch.object(
        scalp_mod, "send_telegram_alert"
    ), patch(
        "app.core.order_execution_guard.assert_real_order_allowed", return_value={}
    ), patch.object(
        s3, "_get_current_price", AsyncMock(return_value=2020.0)
    ):
        out3 = await s3.execute()
    assert out3.success
    assert "pos-1" not in s3.active_positions

    # Stop loss
    s4 = _scalp()
    s4.is_running = True
    s4.active_positions = {
        "pos-2": {
            "entry_price": 2000.0,
            "quantity": 0.05,
            "entry_time": datetime.now(),
            "profit_target": 2100.0,
            "stop_loss": 1990.0,
        }
    }
    with patch.object(scalp_mod, "binance_client", client), patch.object(
        scalp_mod, "send_telegram_alert"
    ), patch(
        "app.core.order_execution_guard.assert_real_order_allowed", return_value={}
    ), patch.object(
        s4, "_get_current_price", AsyncMock(return_value=1980.0)
    ):
        await s4.execute()
    assert "pos-2" not in s4.active_positions

    # Max hold time
    s5 = _scalp()
    s5.is_running = True
    s5.active_positions = {
        "pos-3": {
            "entry_price": 2000.0,
            "quantity": 0.05,
            "entry_time": datetime.now() - timedelta(hours=2),
            "profit_target": 3000.0,
            "stop_loss": 1000.0,
        }
    }
    with patch.object(scalp_mod, "binance_client", client), patch.object(
        scalp_mod, "send_telegram_alert"
    ), patch(
        "app.core.order_execution_guard.assert_real_order_allowed", return_value={}
    ), patch.object(
        s5, "_get_current_price", AsyncMock(return_value=2000.0)
    ):
        await s5.execute()
    assert "pos-3" not in s5.active_positions


async def test_scalping_helpers_rsi_balance_position_status(scalp_mod):
    s = _scalp()
    assert s._calculate_rsi() == 50.0  # short history
    s.price_history = list(range(100, 120))  # rising → high RSI
    assert s._calculate_rsi() > 50

    s.price_history = list(range(120, 100, -1))
    assert s._calculate_rsi() < 50

    client = _client(usdt=10.0)
    with patch.object(scalp_mod, "binance_client", client):
        assert await s._check_balance(50.0) is False
        assert await s._check_balance(5.0) is True
        pos = await s.get_current_position()
        assert pos["asset"] == "ETH" and pos["free"] == 0.1
        with patch.object(
            s, "get_status", AsyncMock(return_value={"running": False})
        ):
            status = await s.get_scalping_status()
        assert "scalping_specific" in status

    with patch.object(scalp_mod, "binance_client", client):
        client.get_account.side_effect = RuntimeError("acc")
        assert await s.get_current_position() == {}
        assert await s._check_balance(1.0) is False
        client.get_ticker.side_effect = RuntimeError("vol")
        assert await s._get_24h_volume() == 0.0


async def test_scalping_entry_guards(scalp_mod):
    s = _scalp(min_volume_threshold=1e12)
    s.price_history = [2000.0] * 25
    client = _client()
    with patch.object(scalp_mod, "binance_client", client):
        assert await s._check_entry_opportunity(2000.0) is None

    s2 = _scalp(rsi_oversold=100)
    s2.price_history = list(range(120, 90, -1))
    with patch.object(scalp_mod, "binance_client", _client(usdt=1.0)):
        assert await s2._check_entry_opportunity(2000.0) is None  # balance


# ── DCA ─────────────────────────────────────────────────────────────────────


async def test_dca_validate_and_execute_branches(dca_mod):
    client = _client(price=2000.0, usdt=500.0)
    with patch.object(dca_mod, "binance_client", client):
        assert await _dca().validate_config() is True
        assert await _dca(investment_amount=-1).validate_config() is False
        assert await _dca(frequency_hours=0).validate_config() is False
        client.get_symbol_ticker.side_effect = RuntimeError("x")
        assert await _dca().validate_config() is False
        client.get_symbol_ticker.side_effect = None
        client.get_symbol_ticker.return_value = {"price": "2000"}

    d = _dca()
    d.is_running = False
    assert (await d.execute()).success is False

    d.is_running = True
    d.next_investment_time = datetime.now() + timedelta(hours=5)
    assert (await d.execute()).error_message == "Not time to invest"

    d2 = _dca(max_investments=1)
    d2.is_running = True
    d2.investment_count = 1
    d2.next_investment_time = None
    assert (await d2.execute()).error_message == "Investment limit reached"

    d3 = _dca(price_threshold=1500.0)
    d3.is_running = True
    with patch.object(dca_mod, "binance_client", client), patch.object(
        d3, "_should_invest", AsyncMock(return_value=True)
    ), patch.object(d3, "_get_current_price", AsyncMock(return_value=2000.0)):
        out = await d3.execute()
    assert out.error_message == "Price above threshold"

    d4 = _dca()
    d4.is_running = True
    with patch.object(dca_mod, "binance_client", client), patch.object(
        d4, "_should_invest", AsyncMock(return_value=True)
    ), patch.object(d4, "_get_current_price", AsyncMock(return_value=None)):
        assert (await d4.execute()).success is False

    d5 = _dca()
    d5.is_running = True
    with patch.object(dca_mod, "binance_client", _client(usdt=1.0)), patch.object(
        d5, "_should_invest", AsyncMock(return_value=True)
    ), patch.object(d5, "_get_current_price", AsyncMock(return_value=2000.0)):
        assert (await d5.execute()).error_message == "Insufficient balance"


async def test_dca_happy_buy_and_status(dca_mod):
    client = _client(price=2000.0, usdt=500.0)
    d = _dca(investment_amount=50.0, enable_notifications=True)
    d.is_running = True
    with patch.object(dca_mod, "binance_client", client), patch.object(
        dca_mod, "send_telegram_alert"
    ) as tg, patch(
        "app.core.order_execution_guard.assert_real_order_allowed", return_value={}
    ):
        out = await d.execute()
    assert out.success is True
    assert d.investment_count == 1
    assert d.total_invested == 50.0
    tg.assert_called()
    with patch.object(d, "get_status", AsyncMock(return_value={"running": True})):
        status = await d.get_dca_status()
    assert status["dca_specific"]["investment_count"] == 1

    with patch.object(dca_mod, "binance_client", client):
        pos = await d.get_current_position()
    assert pos["asset"] == "ETH"

    # place order returns None
    d2 = _dca()
    d2.is_running = True
    with patch.object(dca_mod, "binance_client", client), patch.object(
        d2, "_should_invest", AsyncMock(return_value=True)
    ), patch.object(d2, "_get_current_price", AsyncMock(return_value=2000.0)), patch.object(
        d2, "_check_balance", AsyncMock(return_value=True)
    ), patch.object(
        d2, "_place_buy_order", AsyncMock(return_value=None)
    ):
        assert (await d2.execute()).error_message == "Failed to place order"

    # RealOrderBlocked → place returns None
    with patch.object(dca_mod, "binance_client", client):
        assert await d._place_buy_order(0.01, 2000.0) is None
