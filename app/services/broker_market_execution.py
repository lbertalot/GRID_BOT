"""Órdenes MARKET spot vía ``BrokerAdapter`` (API HTTP, grid, otros callers async)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.binance_async import AsyncBinanceWrapper
from app.services.broker_adapter import (
    BrokerMarketOrderRequest,
    create_broker_adapter_from_env,
)


async def place_spot_market_via_adapter(
    *,
    symbol: str,
    side: str,
    quantity_base: float,
    client_order_id: str | None = None,
    recv_window_ms: int = 10_000,
    binance_wrapper: AsyncBinanceWrapper | None = None,
) -> dict[str, Any]:
    """
    Coloca MARKET en el venue de env; para producción hoy Binance spot.

    ``binance_wrapper``: si se pasa, el adaptador reutiliza ese cliente (p. ej. grid).
    """
    side_u = side.upper()
    if side_u not in ("BUY", "SELL"):
        raise ValueError(f"Lado inválido para MARKET: {side!r}")
    adapter = create_broker_adapter_from_env(binance_wrapper=binance_wrapper)
    req = BrokerMarketOrderRequest(
        symbol_code=symbol.upper(),
        side=side_u,  # type: ignore[arg-type]
        quantity_base=Decimal(str(quantity_base)),
        client_order_id=client_order_id,
        recv_window_ms=recv_window_ms,
    )
    ack = await adapter.place_market_order(req)
    raw = ack.raw
    if not isinstance(raw, dict):
        raise TypeError("BrokerAdapter devolvió raw inválido")
    return raw
