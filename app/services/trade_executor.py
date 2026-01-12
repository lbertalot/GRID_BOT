"""
Trade Executor con actualización automática de balances
Wrapper around Binance orders que integra BalanceService
"""
import logging
import time
import asyncio
import requests
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.binance_client_singleton import get_binance_client_singleton
from app.services.balance_service import BalanceService
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class TradeExecutor:
    """
    Ejecutor de trades que mantiene sincronizados los balances internos
    """
    
    def __init__(self):
        self.binance_client = get_binance_client_singleton()
        self.balance_service = BalanceService()
    
    def execute_order(self, 
                     symbol: str,
                     side: str,
                     order_type: str,
                     quantity: str,
                     db: Optional[Session] = None,
                     update_balance: bool = True,
                     **kwargs) -> Dict[str, Any]:
        """
        Ejecuta una orden y actualiza balances automáticamente
        
        Args:
            symbol: Par de trading (ej: "BTCUSDT")
            side: "BUY" o "SELL"
            order_type: "MARKET", "LIMIT", etc.
            quantity: Cantidad a comprar/vender
            db: Sesión de BD (opcional, se crea una si no se provee)
            update_balance: Si True, actualiza balances automáticamente
            **kwargs: Parámetros adicionales para la orden (price, etc.)
        
        Returns:
            Respuesta de Binance con información de la orden
        
        Raises:
            Exception si la orden falla
        """
        try:
            # 1. Ejecutar orden en Binance (con mitigación -1021)
            logger.info(f"🔄 Ejecutando orden: {side} {quantity} {symbol} ({order_type})")
            # recvWindow amplio para evitar skew menor
            kwargs.setdefault("recvWindow", 10000)
            try:
                order_result = self.binance_client.create_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    **kwargs
                )
            except Exception as e:
                # Mitigación de error -1021: reintentar sincronizando tiempo
                if "-1021" in str(e):
                    try:
                        # ✅ FIX: Envolver requests.get() en thread para no bloquear si se llama desde async
                        # Esta función es sync, pero puede ser llamada desde contextos async
                        # Usar asyncio.to_thread de forma segura
                        try:
                            # Intentar obtener event loop
                            loop = asyncio.get_running_loop()
                            # Si hay loop corriendo, usar asyncio.to_thread
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(
                                    lambda: requests.get("https://api.binance.com/api/v3/time", timeout=3).json()["serverTime"]
                                )
                                srv_time = future.result()
                        except RuntimeError:
                            # No hay event loop, ejecutar directamente (contexto sync)
                            srv_time = requests.get("https://api.binance.com/api/v3/time", timeout=3).json()["serverTime"]
                        
                        now_ms = int(time.time() * 1000)
                        drift = abs(now_ms - int(srv_time))
                        if drift > 1000:
                            # Pequeña espera para reintento
                            # Nota: time.sleep() está bien aquí porque execute_order es sync
                            time.sleep(1.0)
                        # Reintentar
                        kwargs["timestamp"] = int(time.time() * 1000)
                        order_result = self.binance_client.create_order(
                            symbol=symbol,
                            side=side,
                            order_type=order_type,
                            quantity=quantity,
                            **kwargs
                        )
                    except Exception as ee:
                        logger.error(f"❌ Reintento tras -1021 falló: {ee}")
                        raise
                else:
                    raise
            
            # 2. Verificar que se ejecutó
            if not order_result or order_result.get('status') not in ['FILLED', 'PARTIALLY_FILLED']:
                logger.warning(f"⚠️ Orden no ejecutada completamente: {order_result}")
                return order_result
            
            # 3. Actualizar balances internos si está habilitado
            if update_balance:
                self._update_balances_after_trade(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_result=order_result,
                    db=db
                )
            
            logger.info(f"✅ Orden ejecutada: {side} {quantity} {symbol} - OrderID: {order_result.get('orderId')}")
            return order_result
            
        except Exception as e:
            logger.error(f"❌ Error ejecutando orden {side} {quantity} {symbol}: {e}")
            raise
    
    def _update_balances_after_trade(self,
                                     symbol: str,
                                     side: str,
                                     quantity: str,
                                     order_result: Dict[str, Any],
                                     db: Optional[Session] = None):
        """
        Actualiza balances internos después de un trade exitoso
        
        Args:
            symbol: Par de trading (ej: "BTCUSDT")
            side: "BUY" o "SELL"
            quantity: Cantidad ejecutada
            order_result: Respuesta de Binance
            db: Sesión de BD (opcional)
        """
        try:
            # Crear sesión si no existe
            close_db = False
            if db is None:
                db = SessionLocal()
                close_db = True
            
            try:
                # Extraer información de la orden
                executed_qty = Decimal(str(order_result.get('executedQty', quantity)))
                
                # Calcular precio promedio ponderado
                fills = order_result.get('fills', [])
                if fills:
                    total_cost = Decimal('0')
                    total_qty = Decimal('0')
                    for fill in fills:
                        qty = Decimal(str(fill.get('qty', '0')))
                        price = Decimal(str(fill.get('price', '0')))
                        total_cost += qty * price
                        total_qty += qty
                    avg_price = total_cost / total_qty if total_qty > 0 else Decimal('0')
                else:
                    # Si no hay fills, usar el precio de la respuesta
                    avg_price = Decimal(str(order_result.get('price', '0')))
                    if avg_price == 0:
                        # Si no hay precio, intentar obtenerlo del mercado
                        ticker = self.binance_client.get_symbol_ticker(symbol)
                        avg_price = Decimal(str(ticker.get('price', '0')))
                
                # Extraer activos del símbolo (ej: BTCUSDT -> base=BTC, quote=USDT)
                base_asset = symbol[:-4]  # Asume que quote es siempre USDT de 4 caracteres
                quote_asset = symbol[-4:]  # USDT
                
                # Calcular costo total (incluyendo comisión)
                commission = Decimal('0')
                commission_asset = quote_asset
                
                if fills:
                    for fill in fills:
                        comm = Decimal(str(fill.get('commission', '0')))
                        comm_asset = fill.get('commissionAsset', quote_asset)
                        if comm_asset == commission_asset:
                            commission += comm
                
                total_cost = executed_qty * avg_price
                
                # Actualizar balances según el lado
                if side == "BUY":
                    # BUY: -USDT, +Asset
                    cost_with_commission = total_cost + commission
                    BalanceService.update_balance(db, quote_asset, -cost_with_commission)
                    BalanceService.update_balance(db, base_asset, executed_qty)
                    logger.info(
                        f"💰 Balances actualizados (BUY): "
                        f"{quote_asset} -{cost_with_commission:.8f}, "
                        f"{base_asset} +{executed_qty:.8f}"
                    )
                
                elif side == "SELL":
                    # SELL: +USDT, -Asset
                    proceeds = total_cost - commission
                    BalanceService.update_balance(db, base_asset, -executed_qty)
                    BalanceService.update_balance(db, quote_asset, proceeds)
                    logger.info(
                        f"💰 Balances actualizados (SELL): "
                        f"{base_asset} -{executed_qty:.8f}, "
                        f"{quote_asset} +{proceeds:.8f}"
                    )
                
            finally:
                if close_db:
                    db.close()
                    
        except Exception as e:
            logger.error(f"❌ Error actualizando balances después del trade: {e}")
            # No re-raise: la orden ya se ejecutó en Binance
            # Solo loguear el error para investigar
            import traceback
            traceback.print_exc()
    
    def execute_market_buy(self, symbol: str, quantity: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Shortcut para orden MARKET BUY"""
        return self.execute_order(symbol, "BUY", "MARKET", quantity, db=db)
    
    def execute_market_sell(self, symbol: str, quantity: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Shortcut para orden MARKET SELL"""
        return self.execute_order(symbol, "SELL", "MARKET", quantity, db=db)
    
    def execute_limit_buy(self, symbol: str, quantity: str, price: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Shortcut para orden LIMIT BUY"""
        return self.execute_order(symbol, "BUY", "LIMIT", quantity, price=price, db=db, timeInForce="GTC")
    
    def execute_limit_sell(self, symbol: str, quantity: str, price: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Shortcut para orden LIMIT SELL"""
        return self.execute_order(symbol, "SELL", "LIMIT", quantity, price=price, db=db, timeInForce="GTC")


# Instancia global
trade_executor = TradeExecutor()


def get_trade_executor() -> TradeExecutor:
    """Obtiene la instancia global del trade executor"""
    return trade_executor

