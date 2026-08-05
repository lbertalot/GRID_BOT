"""Resolución de `BrokerAdapter` por venue (env y DI opcional)."""

from __future__ import annotations

import os

from app.services.binance_async import AsyncBinanceWrapper
from app.services.broker_adapter.binance_spot import BinanceSpotBrokerAdapter
from app.services.broker_adapter.protocol import BrokerAdapter
from app.services.broker_adapter.stub import UnimplementedVenueBrokerAdapter
from app.services.broker_adapter.types import TradingVenueId


def parse_trading_venue_id(raw: str | None) -> TradingVenueId:
    """Normaliza valor de entorno o config a ``TradingVenueId``."""
    value = (raw or "").strip().lower()
    if value in ("", "binance", "binance_spot"):
        return "binance_spot"
    if value == "byma":
        return "byma"
    if value in ("rofex", "matba_rofex"):
        return "rofex"
    raise ValueError(f"Trading venue desconocido: {raw!r}")


def trading_venue_from_env() -> TradingVenueId:
    return parse_trading_venue_id(os.getenv("BROKER_PRIMARY_VENUE"))


def create_broker_adapter(
    venue: TradingVenueId,
    *,
    binance_wrapper: AsyncBinanceWrapper | None = None,
) -> BrokerAdapter:
    """
    Crea el adaptador para el venue dado.

    Binance reutiliza ``AsyncBinanceWrapper`` (cliente sync en thread + validación).
    """
    if venue == "binance_spot":
        wrap = binance_wrapper or AsyncBinanceWrapper()
        return BinanceSpotBrokerAdapter(wrap)
    if venue in ("byma", "rofex"):
        return UnimplementedVenueBrokerAdapter(venue)
    raise ValueError(f"Venue no soportado: {venue}")


def create_broker_adapter_from_env(
    *,
    binance_wrapper: AsyncBinanceWrapper | None = None,
) -> BrokerAdapter:
    """Versión conveniente para servicios que leen ``BROKER_PRIMARY_VENUE``."""
    return create_broker_adapter(
        trading_venue_from_env(), binance_wrapper=binance_wrapper
    )


def use_broker_adapter_for_trade_execution_from_env() -> bool:
    """
    Flag opt-in: envía órdenes MARKET vía ``BrokerAdapter`` sólo si el venue es Binance spot.

    Requiere ``USE_BROKER_ADAPTER`` truthy y ``BROKER_PRIMARY_VENUE`` compatible (default binance).
    """
    raw = (os.getenv("USE_BROKER_ADAPTER") or "").strip().lower()
    if raw not in {"1", "true", "yes"}:
        return False
    try:
        return trading_venue_from_env() == "binance_spot"
    except ValueError:
        return False
