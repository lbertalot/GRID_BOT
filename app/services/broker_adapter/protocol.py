"""
Contrato `BrokerAdapter` — Fase 0 protocolo Passive Income §8.

Implementaciones concretas: Binance spot (existente), BYMA/Rofex (pendiente).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.services.broker_adapter.types import (
    BrokerBalanceRow,
    BrokerMarketOrderRequest,
    BrokerOpenOrderRow,
    BrokerOrderAck,
    TradingVenueId,
)


@runtime_checkable
class BrokerAdapter(Protocol):
    """Puerto async para lecturas y órdenes spot unificadas por venue."""

    @property
    def venue(self) -> TradingVenueId:
        """Identificador lógico del venue."""

    async def get_last_price(self, symbol_code: str) -> Decimal:
        """Precio de referencia (p. ej. last) en quote del par."""

    async def list_spot_balances(self) -> tuple[BrokerBalanceRow, ...]:
        """Balances spot (libre + bloqueado) en unidades del activo."""

    async def list_open_orders(
        self, symbol_code: str | None
    ) -> tuple[BrokerOpenOrderRow, ...]:
        """Órdenes abiertas; ``symbol_code`` None = todas (si el venue lo permite)."""

    async def place_market_order(
        self, request: BrokerMarketOrderRequest
    ) -> BrokerOrderAck:
        """Orden de mercado spot con validación previa en la implementación."""
