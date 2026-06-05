"""
Tipos neutrales de venue para `BrokerAdapter` (Decimal en dinero/cantidades).

Los `symbol_code` son nativos del venue (p. ej. ``BTCUSDT`` en Binance spot).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TradingVenueId = Literal["binance_spot", "byma", "rofex"]

OrderSide = Literal["BUY", "SELL"]


class BrokerMarketOrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol_code: str = Field(min_length=1, description="Par en notación del venue")
    side: OrderSide
    quantity_base: Decimal = Field(gt=0, description="Cantidad en activo base")
    client_order_id: str | None = Field(
        default=None,
        description="Idempotencia hacia el venue (p. ej. newClientOrderId Binance)",
    )
    recv_window_ms: int | None = Field(
        default=None,
        ge=1,
        le=60_000,
        description="recvWindow API Binance (ms); None = default del cliente",
    )


class BrokerOrderAck(BaseModel):
    model_config = ConfigDict(frozen=True)

    venue_order_id: str
    status: str
    symbol_code: str
    side: OrderSide
    raw: dict[str, Any] = Field(default_factory=dict)


class BrokerBalanceRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    free: Decimal = Field(ge=0)
    locked: Decimal = Field(ge=0)


class BrokerOpenOrderRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol_code: str
    venue_order_id: str
    side: OrderSide
    order_type: str
    quantity: Decimal = Field(gt=0)
    price: Decimal | None = None
    status: str
