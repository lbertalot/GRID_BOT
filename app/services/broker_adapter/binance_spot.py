"""Adaptador Binance spot sobre `AsyncBinanceWrapper` (delegación, sin duplicar validación)."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from app.services.binance_async import AsyncBinanceWrapper
from app.services.broker_adapter.types import (
    BrokerBalanceRow,
    BrokerMarketOrderRequest,
    BrokerOpenOrderRow,
    BrokerOrderAck,
    OrderSide,
    TradingVenueId,
)


def _order_ack_from_binance(
    raw: dict[str, Any], *, symbol: str, side: OrderSide
) -> BrokerOrderAck:
    oid = raw.get("orderId") or raw.get("order_id")
    return BrokerOrderAck(
        venue_order_id=str(oid) if oid is not None else "",
        status=str(raw.get("status", "")),
        symbol_code=symbol.upper(),
        side=side,
        raw=dict(raw),
    )


class BinanceSpotBrokerAdapter:
    """Primera implementación concreta del puerto — mismo proceso que el ciclo actual."""

    def __init__(self, wrapper: AsyncBinanceWrapper) -> None:
        self._w = wrapper

    @property
    def venue(self) -> TradingVenueId:
        return "binance_spot"

    async def get_last_price(self, symbol_code: str) -> Decimal:
        price = await self._w.get_price(symbol_code)
        return Decimal(str(price))

    async def list_spot_balances(self) -> tuple[BrokerBalanceRow, ...]:
        client = self._w.client
        acc = await asyncio.to_thread(client.get_account)
        balances = acc.get("balances") if isinstance(acc, dict) else None
        if not balances:
            return ()
        rows: list[BrokerBalanceRow] = []
        for b in balances:
            if not isinstance(b, dict):
                continue
            asset = str(b.get("asset", ""))
            rows.append(
                BrokerBalanceRow(
                    asset=asset,
                    free=Decimal(str(b.get("free", "0"))),
                    locked=Decimal(str(b.get("locked", "0"))),
                )
            )
        return tuple(rows)

    async def list_open_orders(
        self, symbol_code: str | None
    ) -> tuple[BrokerOpenOrderRow, ...]:
        client = self._w.client
        kwargs: dict[str, Any] = {}
        if symbol_code:
            kwargs["symbol"] = symbol_code.upper()

        raw_list = await asyncio.to_thread(lambda: client.get_open_orders(**kwargs))
        if not raw_list:
            return ()
        out: list[BrokerOpenOrderRow] = []
        for o in raw_list:
            if not isinstance(o, dict):
                continue
            side_raw = str(o.get("side", "BUY")).upper()
            side_parsed: OrderSide = "BUY" if side_raw == "BUY" else "SELL"
            price_raw = o.get("price")
            out.append(
                BrokerOpenOrderRow(
                    symbol_code=str(o.get("symbol", "")),
                    venue_order_id=str(o.get("orderId", "")),
                    side=side_parsed,
                    order_type=str(o.get("type", "")),
                    quantity=Decimal(str(o.get("origQty", o.get("quantity", "0")))),
                    price=Decimal(str(price_raw))
                    if price_raw not in (None, "")
                    else None,
                    status=str(o.get("status", "")),
                )
            )
        return tuple(out)

    async def place_market_order(
        self, request: BrokerMarketOrderRequest
    ) -> BrokerOrderAck:
        raw = await self._w.create_market_order(
            symbol=request.symbol_code,
            side=request.side,
            quantity=float(request.quantity_base),
            new_client_order_id=request.client_order_id,
            recv_window=request.recv_window_ms,
        )
        if not isinstance(raw, dict):
            raise TypeError("create_market_order debe devolver dict")
        return _order_ack_from_binance(
            raw, symbol=request.symbol_code, side=request.side
        )
