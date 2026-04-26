#!/usr/bin/env python3
"""
Estrategia DCA (Dollar Cost Averaging) para Grid Trading Bot

Esta estrategia implementa Dollar Cost Averaging, comprando una cantidad fija
de un activo en intervalos regulares independientemente del precio.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.strategies.base import (
    TradingStrategy,
    StrategyConfig,
    StrategyType,
    TradingResult,
    Order,
    OrderSide,
    OrderStatus,
)

# ✅ FASE 4: Migrado a singleton
from app.services.binance_client_singleton import get_binance_client_singleton

_client_singleton = get_binance_client_singleton()
binance_client = _client_singleton.client if _client_singleton.is_ready() else None
from app.services.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)


class DCAConfig(StrategyConfig):
    """Configuración específica para estrategia DCA"""

    investment_amount: float = 100.0  # Cantidad fija a invertir en USDT
    frequency_hours: int = 24  # Frecuencia de inversión en horas
    max_investments: Optional[int] = (
        None  # Máximo número de inversiones (None = ilimitado)
    )
    price_threshold: Optional[float] = (
        None  # Umbral de precio para comprar (None = siempre)
    )
    enable_notifications: bool = True


class DCAStrategy(TradingStrategy):
    """
    Estrategia DCA (Dollar Cost Averaging)

    Compra una cantidad fija de un activo en intervalos regulares,
    independientemente del precio actual.
    """

    def __init__(self, config: DCAConfig):
        super().__init__(config)
        self.dca_config = config
        self.investment_count = 0
        self.total_invested = 0.0
        self.last_investment_time = None
        self.next_investment_time = None

        logger.info(f"DCA Strategy inicializada para {config.symbol}")

    async def validate_config(self) -> bool:
        """Valida la configuración de la estrategia DCA"""
        try:
            # Validar símbolo
            if not self.config.symbol:
                logger.error("Símbolo no especificado")
                return False

            # Validar cantidad de inversión
            if self.dca_config.investment_amount <= 0:
                logger.error("Cantidad de inversión debe ser mayor a 0")
                return False

            # Validar frecuencia
            if self.dca_config.frequency_hours <= 0:
                logger.error("Frecuencia debe ser mayor a 0")
                return False

            # Verificar que el símbolo existe en Binance
            try:
                import asyncio

                # ✅ FIX: Verificar símbolo (non-blocking)
                ticker = await asyncio.to_thread(
                    binance_client.get_symbol_ticker, symbol=self.config.symbol
                )
                if not ticker:
                    logger.error(
                        f"Símbolo {self.config.symbol} no encontrado en Binance"
                    )
                    return False
            except Exception as e:
                logger.error(f"Error verificando símbolo {self.config.symbol}: {e}")
                return False

            logger.info(f"Configuración DCA válida para {self.config.symbol}")
            return True

        except Exception as e:
            logger.error(f"Error validando configuración DCA: {e}")
            return False

    async def execute(self) -> TradingResult:
        """Ejecuta la estrategia DCA"""
        try:
            if not self.is_running:
                logger.warning("DCA Strategy no está ejecutándose")
                return TradingResult(
                    orders=[],
                    strategy_type=StrategyType.DCA,
                    success=False,
                    error_message="Strategy not running",
                )

            # Verificar si es momento de invertir
            if not await self._should_invest():
                logger.info(f"No es momento de invertir en {self.config.symbol}")
                return TradingResult(
                    orders=[],
                    strategy_type=StrategyType.DCA,
                    success=True,
                    error_message="Not time to invest",
                )

            # Verificar límite de inversiones
            if (
                self.dca_config.max_investments
                and self.investment_count >= self.dca_config.max_investments
            ):
                logger.info(
                    f"Límite de inversiones alcanzado para {self.config.symbol}"
                )
                return TradingResult(
                    orders=[],
                    strategy_type=StrategyType.DCA,
                    success=True,
                    error_message="Investment limit reached",
                )

            # Obtener precio actual
            current_price = await self._get_current_price()
            if not current_price:
                return TradingResult(
                    orders=[],
                    strategy_type=StrategyType.DCA,
                    success=False,
                    error_message="Could not get current price",
                )

            # Verificar umbral de precio
            if (
                self.dca_config.price_threshold
                and current_price > self.dca_config.price_threshold
            ):
                logger.info(
                    f"Precio {current_price} supera umbral {self.dca_config.price_threshold}"
                )
                return TradingResult(
                    orders=[],
                    strategy_type=StrategyType.DCA,
                    success=True,
                    error_message="Price above threshold",
                )

            # Calcular cantidad a comprar
            quantity = self.dca_config.investment_amount / current_price

            # Verificar balance disponible
            if not await self._check_balance(self.dca_config.investment_amount):
                logger.warning(f"Balance insuficiente para DCA en {self.config.symbol}")
                return TradingResult(
                    orders=[],
                    strategy_type=StrategyType.DCA,
                    success=False,
                    error_message="Insufficient balance",
                )

            # Ejecutar orden de compra
            order = await self._place_buy_order(quantity, current_price)

            if order:
                # Actualizar métricas
                self.investment_count += 1
                self.total_invested += self.dca_config.investment_amount
                self.last_investment_time = datetime.now()
                self.next_investment_time = self.last_investment_time + timedelta(
                    hours=self.dca_config.frequency_hours
                )

                # Enviar notificación
                if self.dca_config.enable_notifications:
                    await self._send_notification(order, current_price)

                logger.info(
                    f"DCA ejecutado: {quantity} {self.config.symbol} a ${current_price}"
                )

                return TradingResult(
                    orders=[order],
                    strategy_type=StrategyType.DCA,
                    total_profit=0.0,  # DCA no genera profit inmediato
                    total_volume=self.dca_config.investment_amount,
                    success=True,
                )
            else:
                return TradingResult(
                    orders=[],
                    strategy_type=StrategyType.DCA,
                    success=False,
                    error_message="Failed to place order",
                )

        except Exception as e:
            logger.error(f"Error ejecutando DCA Strategy: {e}")
            return TradingResult(
                orders=[],
                strategy_type=StrategyType.DCA,
                success=False,
                error_message=str(e),
            )

    async def get_current_position(self) -> Dict[str, Any]:
        """Obtiene la posición actual para el símbolo"""
        try:
            import asyncio

            # ✅ FIX: Obtener balance del activo (non-blocking)
            account_info = await asyncio.to_thread(binance_client.get_account)
            asset = self.config.symbol.replace("USDT", "")

            for balance in account_info["balances"]:
                if balance["asset"] == asset:
                    return {
                        "asset": asset,
                        "free": float(balance["free"]),
                        "locked": float(balance["locked"]),
                        "total": float(balance["free"]) + float(balance["locked"]),
                    }

            return {"asset": asset, "free": 0.0, "locked": 0.0, "total": 0.0}

        except Exception as e:
            logger.error(f"Error obteniendo posición DCA: {e}")
            return {}

    async def _should_invest(self) -> bool:
        """Determina si es momento de invertir"""
        if not self.next_investment_time:
            # Primera inversión
            return True

        return datetime.now() >= self.next_investment_time

    async def _get_current_price(self) -> Optional[float]:
        """Obtiene el precio actual del activo"""
        try:
            import asyncio

            # ✅ FIX: Obtener precio (non-blocking)
            ticker = await asyncio.to_thread(
                binance_client.get_symbol_ticker, symbol=self.config.symbol
            )
            return float(ticker["price"])
        except Exception as e:
            logger.error(f"Error obteniendo precio de {self.config.symbol}: {e}")
            return None

    async def _check_balance(self, amount: float) -> bool:
        """Verifica si hay balance suficiente en USDT"""
        try:
            import asyncio

            # ✅ FIX: Verificar balance (non-blocking)
            account_info = await asyncio.to_thread(binance_client.get_account)

            for balance in account_info["balances"]:
                if balance["asset"] == "USDT":
                    free_balance = float(balance["free"])
                    return free_balance >= amount

            return False

        except Exception as e:
            logger.error(f"Error verificando balance: {e}")
            return False

    async def _place_buy_order(self, quantity: float, price: float) -> Optional[Order]:
        """Coloca una orden de compra"""
        try:
            # Crear orden de mercado
            order = binance_client.order_market_buy(
                symbol=self.config.symbol, quantity=quantity
            )

            if order and order.get("orderId"):
                return Order(
                    symbol=self.config.symbol,
                    side=OrderSide.BUY,
                    quantity=quantity,
                    price=price,
                    order_id=str(order["orderId"]),
                    status=OrderStatus.FILLED,
                )

            return None

        except Exception as e:
            logger.error(f"Error colocando orden DCA: {e}")
            return None

    async def _send_notification(self, order: Order, price: float):
        """Envía notificación de la inversión DCA"""
        try:
            message = f"💰 DCA Strategy - {self.config.symbol}\n"
            message += f"Compra: {order.quantity:.6f} {self.config.symbol}\n"
            message += f"Precio: ${price:.4f}\n"
            message += f"Total: ${self.dca_config.investment_amount:.2f}\n"
            message += f"Inversión #{self.investment_count}"

            send_telegram_alert(message)

        except Exception as e:
            logger.error(f"Error enviando notificación DCA: {e}")

    async def get_dca_status(self) -> Dict[str, Any]:
        """Obtiene el estado específico de la estrategia DCA"""
        base_status = await self.get_status()

        return {
            **base_status,
            "dca_specific": {
                "investment_count": self.investment_count,
                "total_invested": self.total_invested,
                "next_investment_time": self.next_investment_time.isoformat()
                if self.next_investment_time
                else None,
                "frequency_hours": self.dca_config.frequency_hours,
                "max_investments": self.dca_config.max_investments,
                "price_threshold": self.dca_config.price_threshold,
            },
        }
