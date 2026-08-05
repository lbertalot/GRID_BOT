"""
Capa BrokerAdapter (Passive Income Fase D / protocolo §8 Fase 0).

Contrato unificado para órdenes y balances; Binance spot es la primera
implementación; BYMA/Rofex permanecen como stubs hasta conectividad acordada.
"""

from __future__ import annotations

from app.services.broker_adapter.binance_spot import BinanceSpotBrokerAdapter
from app.services.broker_adapter.exceptions import BrokerCapabilityError
from app.services.broker_adapter.factory import (
    create_broker_adapter,
    create_broker_adapter_from_env,
    parse_trading_venue_id,
    trading_venue_from_env,
    use_broker_adapter_for_trade_execution_from_env,
)
from app.services.broker_adapter.protocol import BrokerAdapter
from app.services.broker_adapter.stub import UnimplementedVenueBrokerAdapter
from app.services.broker_adapter.types import (
    BrokerBalanceRow,
    BrokerMarketOrderRequest,
    BrokerOpenOrderRow,
    BrokerOrderAck,
    TradingVenueId,
)

__all__ = [
    "BinanceSpotBrokerAdapter",
    "BrokerAdapter",
    "BrokerBalanceRow",
    "BrokerCapabilityError",
    "BrokerMarketOrderRequest",
    "BrokerOpenOrderRow",
    "BrokerOrderAck",
    "TradingVenueId",
    "UnimplementedVenueBrokerAdapter",
    "create_broker_adapter",
    "create_broker_adapter_from_env",
    "parse_trading_venue_id",
    "trading_venue_from_env",
    "use_broker_adapter_for_trade_execution_from_env",
]
