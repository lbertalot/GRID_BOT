"""Adaptadores no implementados para venues futuros (BYMA / Rofex)."""

from __future__ import annotations

from decimal import Decimal

from app.services.broker_adapter.exceptions import BrokerCapabilityError
from app.services.broker_adapter.types import (
    BrokerBalanceRow,
    BrokerMarketOrderRequest,
    BrokerOpenOrderRow,
    BrokerOrderAck,
    TradingVenueId,
)


class UnimplementedVenueBrokerAdapter:
    """Place-holder hasta conectividad read-only u órdenes (protocolo §8.1–8.2)."""

    def __init__(self, venue: TradingVenueId) -> None:
        self._venue: TradingVenueId = venue

    @property
    def venue(self) -> TradingVenueId:
        return self._venue

    async def get_last_price(self, symbol_code: str) -> Decimal:
        raise BrokerCapabilityError(
            f"{self._venue}: get_last_price no implementado (Fase D)"
        )

    async def list_spot_balances(self) -> tuple[BrokerBalanceRow, ...]:
        raise BrokerCapabilityError(
            f"{self._venue}: list_spot_balances no implementado (Fase D)"
        )

    async def list_open_orders(
        self, symbol_code: str | None
    ) -> tuple[BrokerOpenOrderRow, ...]:
        raise BrokerCapabilityError(
            f"{self._venue}: list_open_orders no implementado (Fase D)"
        )

    async def place_market_order(
        self, request: BrokerMarketOrderRequest
    ) -> BrokerOrderAck:
        raise BrokerCapabilityError(
            f"{self._venue}: place_market_order no implementado (Fase D)"
        )
