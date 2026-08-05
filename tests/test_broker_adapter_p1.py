"""P1: contrato BrokerAdapter + factory + adaptador Binance spot (delegación)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.broker_adapter import (
    BinanceSpotBrokerAdapter,
    BrokerCapabilityError,
    BrokerMarketOrderRequest,
    UnimplementedVenueBrokerAdapter,
    create_broker_adapter,
    create_broker_adapter_from_env,
    parse_trading_venue_id,
)
from app.services.binance_async import AsyncBinanceWrapper


def test_parse_trading_venue_defaults_to_binance_spot() -> None:
    assert parse_trading_venue_id(None) == "binance_spot"
    assert parse_trading_venue_id("") == "binance_spot"
    assert parse_trading_venue_id("binance") == "binance_spot"


def test_parse_trading_venue_byma_rofex() -> None:
    assert parse_trading_venue_id("byma") == "byma"
    assert parse_trading_venue_id("rofex") == "rofex"
    assert parse_trading_venue_id("matba_rofex") == "rofex"


def test_use_broker_adapter_trade_execution_requires_binance_spot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.broker_adapter import (
        use_broker_adapter_for_trade_execution_from_env,
    )

    monkeypatch.setenv("USE_BROKER_ADAPTER", "true")
    monkeypatch.setenv("BROKER_PRIMARY_VENUE", "byma")
    assert use_broker_adapter_for_trade_execution_from_env() is False


def test_factory_returns_binance_adapter() -> None:
    ad = create_broker_adapter("binance_spot")
    assert isinstance(ad, BinanceSpotBrokerAdapter)
    assert ad.venue == "binance_spot"


def test_factory_returns_stub_for_byma() -> None:
    ad = create_broker_adapter("byma")
    assert isinstance(ad, UnimplementedVenueBrokerAdapter)


@pytest.mark.asyncio
async def test_unimplemented_venue_raises_capability() -> None:
    ad = UnimplementedVenueBrokerAdapter("rofex")
    with pytest.raises(BrokerCapabilityError, match="rofex"):
        await ad.get_last_price("USD/ARS")


@pytest.mark.asyncio
async def test_binance_adapter_last_price_uses_wrapper() -> None:
    w = AsyncBinanceWrapper()
    ad = BinanceSpotBrokerAdapter(w)
    price = await ad.get_last_price("BTCUSDT")
    assert price > 0


@pytest.mark.asyncio
async def test_binance_adapter_balances_from_client() -> None:
    w = AsyncBinanceWrapper()

    def fake_get_account() -> dict:
        return {"balances": [{"asset": "USDT", "free": "12.5", "locked": "1.0"}]}

    w.client.get_account = fake_get_account  # type: ignore[assignment]
    ad = BinanceSpotBrokerAdapter(w)
    rows = await ad.list_spot_balances()
    assert len(rows) == 1
    assert rows[0].asset == "USDT"
    assert rows[0].free == Decimal("12.5")
    assert rows[0].locked == Decimal("1.0")


@pytest.mark.asyncio
async def test_binance_adapter_open_orders_from_client() -> None:
    w = AsyncBinanceWrapper()

    def fake_open(**_kwargs: object) -> list[dict]:
        return [
            {
                "symbol": "BTCUSDT",
                "orderId": 42,
                "side": "SELL",
                "type": "LIMIT",
                "origQty": "0.01",
                "price": "50000",
                "status": "NEW",
            }
        ]

    w.client.get_open_orders = fake_open  # type: ignore[assignment]
    ad = BinanceSpotBrokerAdapter(w)
    rows = await ad.list_open_orders("BTCUSDT")
    assert len(rows) == 1
    assert rows[0].venue_order_id == "42"
    assert rows[0].side == "SELL"


@pytest.mark.asyncio
async def test_create_broker_adapter_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BROKER_PRIMARY_VENUE", "binance_spot")
    ad = create_broker_adapter_from_env()
    assert isinstance(ad, BinanceSpotBrokerAdapter)


@pytest.mark.asyncio
async def test_binance_place_market_delegates_to_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = AsyncBinanceWrapper()

    async def fake_create(
        symbol: str, side: str, quantity: float, **kwargs: object
    ) -> dict:
        _ = kwargs
        return {"orderId": 7, "status": "FILLED", "symbol": symbol}

    monkeypatch.setattr(w, "create_market_order", fake_create)
    ad = BinanceSpotBrokerAdapter(w)
    req = BrokerMarketOrderRequest(
        symbol_code="btcusdt", side="BUY", quantity_base=Decimal("0.001")
    )
    ack = await ad.place_market_order(req)
    assert ack.venue_order_id == "7"
    assert ack.status == "FILLED"
    assert ack.side == "BUY"


@pytest.mark.asyncio
async def test_binance_async_market_forwards_client_order_recv_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = AsyncBinanceWrapper()
    calls: list[dict[str, object]] = []

    def fake_create_order(**kwargs: object) -> dict:
        calls.append(kwargs)
        return {"orderId": 1, "status": "FILLED", "symbol": "BTCUSDT"}

    w.client.create_order = fake_create_order  # type: ignore[assignment]
    monkeypatch.setattr(
        w.validator,
        "validate_order_parameters",
        lambda *_a, **_k: {
            "is_valid": True,
            "quantity_info": {"adjusted_quantity": 0.01},
            "errors": [],
        },
    )
    await w.create_market_order(
        "BTCUSDT",
        "BUY",
        0.01,
        new_client_order_id="co-probe",
        recv_window=7777,
    )
    assert len(calls) == 1
    assert calls[0]["newClientOrderId"] == "co-probe"
    assert calls[0]["recvWindow"] == 7777
