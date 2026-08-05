#!/usr/bin/env python3
"""
Estrategia de Scalping para Grid Trading Bot

Esta estrategia implementa scalping, buscando pequeñas ganancias en movimientos
rápidos de precio con tiempos de retención muy cortos.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np

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


class ScalpingConfig(StrategyConfig):
    """Configuración específica para estrategia de Scalping"""

    # Parámetros de entrada
    entry_threshold: float = 0.002  # 0.2% de movimiento para entrar
    profit_target: float = 0.005  # 0.5% de ganancia objetivo
    stop_loss: float = 0.003  # 0.3% de pérdida máxima
    max_position_size: float = 100.0  # Tamaño máximo de posición en USDT

    # Parámetros de tiempo
    max_hold_time_minutes: int = 30  # Tiempo máximo de retención
    min_volume_threshold: float = 1000000  # Volumen mínimo en 24h

    # Parámetros técnicos
    rsi_oversold: int = 30  # RSI para considerar sobreventa
    rsi_overbought: int = 70  # RSI para considerar sobrecompra
    enable_notifications: bool = True


class ScalpingStrategy(TradingStrategy):
    """
    Estrategia de Scalping

    Busca pequeñas ganancias en movimientos rápidos de precio
    con tiempos de retención muy cortos.
    """

    def __init__(self, config: ScalpingConfig):
        super().__init__(config)
        self.scalping_config = config
        self.active_positions: Dict[str, Dict] = {}
        self.price_history: List[float] = []
        self.last_analysis_time = None

        logger.info(f"Scalping Strategy inicializada para {config.symbol}")

    async def validate_config(self) -> bool:
        """Valida la configuración de la estrategia de Scalping"""
        try:
            # Validar símbolo
            if not self.config.symbol:
                logger.error("Símbolo no especificado")
                return False

            # Validar umbrales
            if self.scalping_config.entry_threshold <= 0:
                logger.error("Entry threshold debe ser mayor a 0")
                return False

            if self.scalping_config.profit_target <= 0:
                logger.error("Profit target debe ser mayor a 0")
                return False

            if self.scalping_config.stop_loss <= 0:
                logger.error("Stop loss debe ser mayor a 0")
                return False

            # Verificar que profit target > stop loss
            if self.scalping_config.profit_target <= self.scalping_config.stop_loss:
                logger.error("Profit target debe ser mayor que stop loss")
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

            logger.info(f"Configuración Scalping válida para {self.config.symbol}")
            return True

        except Exception as e:
            logger.error(f"Error validando configuración Scalping: {e}")
            return False

    async def execute(self) -> TradingResult:
        """Ejecuta la estrategia de Scalping"""
        try:
            if not self.is_running:
                logger.warning("Scalping Strategy no está ejecutándose")
                return TradingResult(
                    orders=[],
                    strategy_type=StrategyType.SCALPING,
                    success=False,
                    error_message="Strategy not running",
                )

            # Obtener precio actual
            current_price = await self._get_current_price()
            if not current_price:
                return TradingResult(
                    orders=[],
                    strategy_type=StrategyType.SCALPING,
                    success=False,
                    error_message="Could not get current price",
                )

            # Actualizar historial de precios
            self.price_history.append(current_price)
            if len(self.price_history) > 100:  # Mantener solo últimos 100 precios
                self.price_history.pop(0)

            orders = []

            # Verificar posiciones activas
            if self.active_positions:
                orders.extend(await self._manage_active_positions(current_price))

            # Buscar nuevas oportunidades
            if len(orders) == 0:  # Solo si no hay órdenes de salida
                entry_order = await self._check_entry_opportunity(current_price)
                if entry_order:
                    orders.append(entry_order)

            self.last_analysis_time = datetime.now()

            return TradingResult(
                orders=orders,
                strategy_type=StrategyType.SCALPING,
                total_profit=sum(
                    order.quantity * order.price
                    for order in orders
                    if order.side == OrderSide.SELL
                ),
                total_volume=sum(order.quantity * order.price for order in orders),
                success=True,
            )

        except Exception as e:
            logger.error(f"Error ejecutando Scalping Strategy: {e}")
            return TradingResult(
                orders=[],
                strategy_type=StrategyType.SCALPING,
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
                        "active_positions": len(self.active_positions),
                    }

            return {
                "asset": asset,
                "free": 0.0,
                "locked": 0.0,
                "total": 0.0,
                "active_positions": len(self.active_positions),
            }

        except Exception as e:
            logger.error(f"Error obteniendo posición Scalping: {e}")
            return {}

    async def _check_entry_opportunity(self, current_price: float) -> Optional[Order]:
        """Verifica si hay oportunidad de entrada"""
        try:
            if len(self.price_history) < 20:
                return None  # Necesitamos más datos históricos

            # Calcular indicadores técnicos
            rsi = self._calculate_rsi()
            volume_24h = await self._get_24h_volume()

            # Verificar condiciones de entrada
            if volume_24h < self.scalping_config.min_volume_threshold:
                return None  # Volumen insuficiente

            # Verificar RSI para sobreventa (oportunidad de compra)
            if rsi < self.scalping_config.rsi_oversold:
                # Calcular cantidad basada en el tamaño máximo de posición
                quantity = self.scalping_config.max_position_size / current_price

                # Verificar balance
                if not await self._check_balance(
                    self.scalping_config.max_position_size
                ):
                    return None

                # Colocar orden de compra
                order = await self._place_buy_order(quantity, current_price)

                if order:
                    # Registrar posición activa
                    self.active_positions[order.order_id] = {
                        "entry_price": current_price,
                        "quantity": quantity,
                        "entry_time": datetime.now(),
                        "profit_target": current_price
                        * (1 + self.scalping_config.profit_target),
                        "stop_loss": current_price
                        * (1 - self.scalping_config.stop_loss),
                    }

                    logger.info(
                        f"Scalping entrada: {quantity} {self.config.symbol} a ${current_price}"
                    )

                    if self.scalping_config.enable_notifications:
                        await self._send_entry_notification(order, current_price, rsi)

                return order

            return None

        except Exception as e:
            logger.error(f"Error verificando oportunidad de entrada: {e}")
            return None

    async def _manage_active_positions(self, current_price: float) -> List[Order]:
        """Gestiona las posiciones activas"""
        orders = []
        positions_to_remove = []

        for order_id, position in self.active_positions.items():
            entry_price = position["entry_price"]
            profit_target = position["profit_target"]
            stop_loss = position["stop_loss"]
            entry_time = position["entry_time"]
            quantity = position["quantity"]

            # Verificar si es momento de vender
            should_sell = False
            sell_reason = ""

            # Verificar profit target
            if current_price >= profit_target:
                should_sell = True
                sell_reason = "Profit target reached"

            # Verificar stop loss
            elif current_price <= stop_loss:
                should_sell = True
                sell_reason = "Stop loss triggered"

            # Verificar tiempo máximo de retención
            elif datetime.now() - entry_time >= timedelta(
                minutes=self.scalping_config.max_hold_time_minutes
            ):
                should_sell = True
                sell_reason = "Max hold time reached"

            if should_sell:
                # Colocar orden de venta
                sell_order = await self._place_sell_order(quantity, current_price)

                if sell_order:
                    orders.append(sell_order)
                    positions_to_remove.append(order_id)

                    # Calcular ganancia/pérdida
                    profit = (current_price - entry_price) * quantity

                    logger.info(
                        f"Scalping salida: {quantity} {self.config.symbol} a ${current_price} - {sell_reason}"
                    )

                    if self.scalping_config.enable_notifications:
                        await self._send_exit_notification(
                            sell_order, current_price, profit, sell_reason
                        )

        # Remover posiciones cerradas
        for order_id in positions_to_remove:
            del self.active_positions[order_id]

        return orders

    def _calculate_rsi(self, period: int = 14) -> float:
        """Calcula el RSI (Relative Strength Index)"""
        try:
            if len(self.price_history) < period + 1:
                return 50.0  # Valor neutral si no hay suficientes datos

            prices = np.array(self.price_history[-period - 1 :])
            deltas = np.diff(prices)

            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return float(rsi)

        except Exception as e:
            logger.error(f"Error calculando RSI: {e}")
            return 50.0

    async def _get_24h_volume(self) -> float:
        """Obtiene el volumen de 24 horas"""
        try:
            ticker_24h = binance_client.get_ticker(symbol=self.config.symbol)
            return float(ticker_24h["volume"]) * float(ticker_24h["lastPrice"])
        except Exception as e:
            logger.error(f"Error obteniendo volumen 24h: {e}")
            return 0.0

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
            from app.core.order_execution_guard import assert_real_order_allowed

            assert_real_order_allowed(context="ScalpingStrategy._place_buy_order")
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
            logger.error(f"Error colocando orden de compra Scalping: {e}")
            return None

    async def _place_sell_order(self, quantity: float, price: float) -> Optional[Order]:
        """Coloca una orden de venta"""
        try:
            from app.core.order_execution_guard import assert_real_order_allowed

            assert_real_order_allowed(context="ScalpingStrategy._place_sell_order")
            order = binance_client.order_market_sell(
                symbol=self.config.symbol, quantity=quantity
            )

            if order and order.get("orderId"):
                return Order(
                    symbol=self.config.symbol,
                    side=OrderSide.SELL,
                    quantity=quantity,
                    price=price,
                    order_id=str(order["orderId"]),
                    status=OrderStatus.FILLED,
                )

            return None

        except Exception as e:
            logger.error(f"Error colocando orden de venta Scalping: {e}")
            return None

    async def _send_entry_notification(self, order: Order, price: float, rsi: float):
        """Envía notificación de entrada"""
        try:
            message = f"📈 Scalping Entry - {self.config.symbol}\n"
            message += f"Compra: {order.quantity:.6f} {self.config.symbol}\n"
            message += f"Precio: ${price:.4f}\n"
            message += f"RSI: {rsi:.1f}\n"
            message += f"Posiciones activas: {len(self.active_positions)}"

            send_telegram_alert(message)

        except Exception as e:
            logger.error(f"Error enviando notificación de entrada: {e}")

    async def _send_exit_notification(
        self, order: Order, price: float, profit: float, reason: str
    ):
        """Envía notificación de salida"""
        try:
            message = f"📉 Scalping Exit - {self.config.symbol}\n"
            message += f"Venta: {order.quantity:.6f} {self.config.symbol}\n"
            message += f"Precio: ${price:.4f}\n"
            message += f"Profit: ${profit:.2f}\n"
            message += f"Razón: {reason}"

            send_telegram_alert(message)

        except Exception as e:
            logger.error(f"Error enviando notificación de salida: {e}")

    async def get_scalping_status(self) -> Dict[str, Any]:
        """Obtiene el estado específico de la estrategia de Scalping"""
        base_status = await self.get_status()

        return {
            **base_status,
            "scalping_specific": {
                "active_positions": len(self.active_positions),
                "positions": self.active_positions,
                "price_history_length": len(self.price_history),
                "last_analysis_time": self.last_analysis_time.isoformat()
                if self.last_analysis_time
                else None,
                "current_rsi": self._calculate_rsi() if self.price_history else None,
            },
        }
