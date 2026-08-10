"""COV-3.4 — trade_executor / order_validation / commission_manager gaps.

Paper-only · no live · PROMOTE_LIVE: NO.
Decimal en fees/qty; paper iso commission; validation edges.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.commission_manager import CommissionManager
from app.services.order_validation import OrderValidator
from app.services.trade_executor import (
    TradeExecutor,
    _trade_executor_adapter_kwargs_ok,
)

pytestmark = pytest.mark.usefixtures("allow_real_orders_unit")


# ── CommissionManager (paper iso + math) ─────────────────────────────────────


@pytest.fixture
def paper_cm(paper_env, monkeypatch) -> CommissionManager:
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    return CommissionManager()


def test_commission_math_and_grid(paper_cm):
    cm = paper_cm
    rates = cm.get_commission_rates("BTCUSDT")
    assert rates["maker"] == 0.001 and rates["taker"] == 0.001
    assert cm.get_commission_rates("BTCUSDT") is cm._commission_cache["BTCUSDT"]

    assert cm.calculate_commission(1000.0, "MARKET") == pytest.approx(1.0)
    assert cm.calculate_commission(1000.0, "LIMIT") == pytest.approx(1.0)

    assert cm.calculate_net_quantity(1.0, 100.0, "BUY") == 1.0
    net_sell = cm.calculate_net_quantity(1.0, 100.0, "SELL", "MARKET")
    assert 0 < net_sell < 1.0

    assert cm.calculate_required_quantity_for_target(1.0, 100.0, "BUY") == 1.0
    req = cm.calculate_required_quantity_for_target(1.0, 100.0, "SELL", "MARKET")
    assert req > 1.0

    profit = cm.calculate_profit_with_commissions(100.0, 110.0, 1.0)
    assert profit["gross_profit"] == pytest.approx(10.0)
    assert profit["net_profit"] < profit["gross_profit"]
    assert profit["profit_percentage"] > 0

    ok, detail = cm.validate_minimum_profit(100.0, 110.0, 1.0, min_profit_percentage=0.5)
    assert ok is True and detail["net_profit"] > 0
    bad, _ = cm.validate_minimum_profit(100.0, 100.1, 1.0, min_profit_percentage=5.0)
    assert bad is False

    grid = cm.adjust_grid_levels_for_commissions(
        min_price=100.0,
        max_price=110.0,
        num_levels=5,
        quantity=0.01,
        min_profit_percentage=0.5,
        symbol="BTCUSDT",
    )
    assert grid["adjusted_spacing"] >= grid["original_spacing"]
    assert len(grid["adjusted_levels"]) >= 2
    assert grid["profitability_analysis"]
    assert grid["commission_per_trade"] > 0


def test_commission_update_rates_paper_and_client(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    cm = CommissionManager()
    cm.client = MagicMock()
    cm._update_commission_rates()  # no-op en paper
    cm.client.get_account.assert_not_called()

    monkeypatch.setenv("PAPER_TRADING", "false")
    cm.client = None
    cm._update_commission_rates()

    cm.client = MagicMock()
    cm.client.get_account.side_effect = RuntimeError("boom")
    cm._update_commission_rates()  # warning path

    monkeypatch.setenv("BINANCE_API_KEY", "k" * 32)
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s" * 32)
    mock_cli = MagicMock()
    mock_cli.get_account.return_value = {
        "makerCommission": 10,
        "takerCommission": 15,
    }
    with patch(
        "app.services.commission_manager.Client", return_value=mock_cli
    ), patch(
        "app.services.commission_manager.get_binance_proxies",
        return_value={"https": "http://p"},
    ):
        live = CommissionManager()
    assert live.default_maker_commission == pytest.approx(0.001)
    assert live.default_taker_commission == pytest.approx(0.0015)

    with patch(
        "app.services.commission_manager.Client", side_effect=RuntimeError("init")
    ), patch(
        "app.services.commission_manager.get_binance_proxies", return_value=None
    ):
        broken = CommissionManager()
    assert broken.client is None


# ── OrderValidator edges ─────────────────────────────────────────────────────


def _sym_info(**overrides):
    base = {
        "symbol": "BTCUSDT",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "stepSize": 0.001,
        "minQty": 0.001,
        "maxQty": 10.0,
        "minNotional": 10.0,
        "tickSize": 0.01,
        "minPrice": 100.0,
        "maxPrice": 200.0,
        "pricePrecision": 8,
        "quantityPrecision": 8,
    }
    base.update(overrides)
    return base


def test_order_validation_edges():
    client = MagicMock()
    v = OrderValidator(client)
    # cliente sin use_cache kw — rama get_exchange_info() directa
    client.get_exchange_info = MagicMock(
        side_effect=TypeError("no use_cache")
    )
    # forzar hasattr True pero TypeError → except → None? Actually hasattr is True
    # and call fails → except returns None
    assert v.get_symbol_info("BTCUSDT") is None

    client2 = MagicMock(spec=[])  # no get_exchange_info attr... wait Client always has it
    # Simular client sin método: use object without get_exchange_info
    class _C:
        pass

    c = _C()
    c.get_exchange_info = MagicMock(  # type: ignore[attr-defined]
        return_value={
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "quotePrecision": 8,
                    "baseAssetPrecision": 8,
                    "filters": [
                        {
                            "filterType": "LOT_SIZE",
                            "stepSize": "0.001",
                            "minQty": "0.001",
                            "maxQty": "1000",
                        },
                        {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                        {
                            "filterType": "PRICE_FILTER",
                            "tickSize": "0.01",
                            "minPrice": "0",
                            "maxPrice": "0",
                        },
                    ],
                }
            ]
        }
    )
    # hasattr True → use_cache=True path; if TypeError on use_cache, whole get fails
    c.get_exchange_info = MagicMock(
        side_effect=lambda **kw: {
            "symbols": [
                {
                    "symbol": "ETHUSDT",
                    "baseAsset": "ETH",
                    "quoteAsset": "USDT",
                    "quotePrecision": 8,
                    "baseAssetPrecision": 8,
                    "filters": [
                        {
                            "filterType": "LOT_SIZE",
                            "stepSize": "0.01",
                            "minQty": "0.01",
                            "maxQty": "100",
                        },
                        {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
                        {
                            "filterType": "PRICE_FILTER",
                            "tickSize": "0.01",
                            "minPrice": "1",
                            "maxPrice": "10000",
                        },
                    ],
                }
            ]
        }
        if kw.get("use_cache")
        else (_ for _ in ()).throw(TypeError("no kw"))
    )
    v2 = OrderValidator(c)  # type: ignore[arg-type]
    info = v2.get_symbol_info("ETHUSDT")
    assert info and info["stepSize"] == 0.01

    # round edges
    assert v._round_to_step(1.234, 0) == 1.234
    assert v._round_to_tick(1.239, 0) == 1.239

    v3 = OrderValidator(MagicMock())
    with patch.object(v3, "get_symbol_info", side_effect=RuntimeError("x")):
        adj = v3.adjust_quantity_precision(1.0, "BTCUSDT")
        assert "error" in adj and adj["adjusted_quantity"] == 1.0

    v3.get_symbol_info = MagicMock(return_value=_sym_info())  # type: ignore
    v3.client.get_symbol_ticker.return_value = {"price": "150"}
    low = v3.validate_order_parameters("BTCUSDT", 0.1, "BUY", "LIMIT", price=50.0)
    assert low["is_valid"] is False and "mínimo" in low["errors"][0].lower()
    high = v3.validate_order_parameters("BTCUSDT", 0.1, "BUY", "LIMIT", price=250.0)
    assert high["is_valid"] is False and "máximo" in high["errors"][0].lower()


# ── TradeExecutor gaps ───────────────────────────────────────────────────────


def test_trade_executor_breakers_ticker_and_adapter_side():
    assert _trade_executor_adapter_kwargs_ok({"recvWindow": 1})
    assert not _trade_executor_adapter_kwargs_ok({"price": 1})

    ex = TradeExecutor()
    ex.binance_client = MagicMock()

    cb = MagicMock()
    cb.is_trading_halted.return_value = True
    cb.get_all_breakers_status.return_value = {"active_breakers": ["max_dd"]}
    with patch("app.core.circuit_breakers.CircuitBreakers", return_value=cb):
        with pytest.raises(ValueError, match="Circuit Breaker"):
            ex.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")

    cb.is_trading_halted.side_effect = RuntimeError("cb down")
    ex.binance_client.create_order.return_value = {
        "status": "NEW",
        "orderId": 1,
    }
    with patch("app.core.circuit_breakers.CircuitBreakers", return_value=cb):
        out = ex.execute_order("BTCUSDT", "BUY", "MARKET", "0.001", update_balance=False)
    assert out["status"] == "NEW"

    with patch(
        "app.services.trade_executor.BalanceService.update_balance"
    ), patch("app.services.trade_executor.SessionLocal") as sess:
        sess.return_value = MagicMock()
        ex.binance_client.get_symbol_ticker.return_value = {"price": "42000"}
        ex._update_balances_after_trade(
            "BTCUSDT",
            "BUY",
            "0.001",
            {"status": "FILLED", "executedQty": "0.001", "price": "0", "fills": []},
        )
        ex.binance_client.get_symbol_ticker.assert_called()

    with pytest.raises(ValueError, match="Lado inválido"):
        ex._execute_market_via_broker_adapter(
            symbol="BTCUSDT",
            side="HOLD",
            quantity="0.001",
            recv_window=1000,
            client_order_id=None,
        )

    # adapter -1021 fallback a legacy
    filled = {
        "status": "FILLED",
        "orderId": 9,
        "executedQty": "0.001",
        "fills": [
            {
                "qty": "0.001",
                "price": "50000",
                "commission": "0",
                "commissionAsset": "USDT",
            }
        ],
    }
    ex.binance_client.create_order.return_value = filled
    with patch(
        "app.services.trade_executor.use_broker_adapter_for_trade_execution_from_env",
        return_value=True,
    ), patch.object(
        ex,
        "_execute_market_via_broker_adapter",
        side_effect=RuntimeError("timestamp -1021"),
    ), patch(
        "app.services.trade_executor.BalanceService.update_balance"
    ), patch(
        "app.core.circuit_breakers.CircuitBreakers"
    ) as CB:
        CB.return_value.is_trading_halted.return_value = False
        result = ex.execute_order("BTCUSDT", "BUY", "MARKET", "0.001")
    assert result["orderId"] == 9
