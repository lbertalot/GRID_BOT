import os
import time
import logging
from typing import Dict, Any, Optional, List
import math
from decimal import Decimal, ROUND_DOWN, getcontext

USE_REAL = os.getenv("USE_REAL_BINANCE", "0") == "1"
if not USE_REAL:

    class _DummyEx(Exception):
        pass

    class _DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_account(self, *args, **kwargs):
            return {"balances": []}

        def get_asset_balance(self, asset: str):
            return {"asset": asset, "free": "0", "locked": "0"}

        def get_symbol_ticker(self, symbol: str):
            return {"symbol": symbol, "price": "100.0"}

        def get_exchange_info(self):
            return {"symbols": []}

        def order_market_buy(self, *args, **kwargs):
            return {"orderId": 1, "status": "FILLED", "fills": []}

        def order_market_sell(self, *args, **kwargs):
            return {"orderId": 2, "status": "FILLED", "fills": []}

        def order_limit_buy(self, *args, **kwargs):
            return {"orderId": 3, "status": "NEW", "fills": []}

        def order_limit_sell(self, *args, **kwargs):
            return {"orderId": 4, "status": "NEW", "fills": []}

        def cancel_order(self, *args, **kwargs):
            return {"status": "CANCELED"}

    Client = _DummyClient  # type: ignore
    BinanceAPIException = _DummyEx  # type: ignore
else:
    from binance import Client
    from binance.exceptions import BinanceAPIException
import tenacity
from app.core.config import settings
from app.services.commission_manager import commission_manager
from app.core.redis_cache import redis_cache

# from app.core.metrics import record_binance_api_call, binance_connection_status

logger = logging.getLogger(__name__)


class BinanceService:
    """Servicio para interactuar con la API de Binance"""

    def __init__(self):
        """Ejecuta __init__."""
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_SECRET_KEY", "")
        # ✅ FASE 4: Usar singleton en lugar de crear nuevo cliente
        try:
            from app.services.binance_client_singleton import (
                get_binance_client_singleton,
            )

            singleton = get_binance_client_singleton()
            if singleton.is_ready():
                self.client = singleton.client
            else:
                # Fallback si singleton no está listo
                self.client = Client(
                    self.api_key, self.api_secret, testnet=settings.binance_testnet
                )
        except Exception as e:
            logger.warning(f"No se pudo usar singleton, creando cliente directo: {e}")
            self.client = Client(
                self.api_key, self.api_secret, testnet=settings.binance_testnet
            )

        # Cache para información de símbolos
        self._symbol_info_cache = {}

        # Cache Redis para optimización de latencia
        self.redis_cache = redis_cache

        # Inicializar modo simulación (paper/testnet fuerza simulación)
        self.simulation_mode = (
            bool(settings.paper_trading)
            or bool(settings.binance_testnet)
            or os.getenv("PAPER_TRADING", "false").lower() == "true"
            or os.getenv("BINANCE_TESTNET", "false").lower() == "true"
        )
        # Permitir forzar modo real ignorando PAPER_TRADING
        self.force_real_mode = os.getenv("FORCE_REAL_MODE", "false").lower() == "true"
        if self.force_real_mode:
            self.simulation_mode = False

        # Inicializar cliente automáticamente
        self._initialize_client()

    def _initialize_client(self):
        """Inicializa el cliente de Binance con manejo de errores"""
        try:
            # Si está forzado modo real, no activar simulación por PAPER_TRADING
            if self.simulation_mode and not self.force_real_mode:
                logger.info(
                    "📄 PAPER_TRADING activo: habilitando modo simulación en BinanceService"
                )
                return

            if not self.api_key or not self.api_secret:
                if self.force_real_mode:
                    raise ValueError(
                        "Credenciales de Binance no configuradas y FORCE_REAL_MODE=true"
                    )
                else:
                    logger.warning(
                        "Credenciales de Binance no configuradas. Activando modo simulación."
                    )
                    self.simulation_mode = True
                    # binance_connection_status.set(0)
                    return

            # Intentar crear el cliente
            self.client = Client(
                self.api_key, self.api_secret, testnet=settings.binance_testnet
            )

            # Verificar credenciales con una llamada simple si no estamos en PAPER_TRADING
            if not self.simulation_mode:
                start_time = time.time()
                try:
                    account_info = self.client.get_account(recvWindow=10000)
                except BinanceAPIException as e:
                    if e.code == -2015:
                        logger.error(
                            f"❌ Binance -2015 (IP/Permisos). Activando simulación: {e}"
                        )
                        self.simulation_mode = True
                        return
                    raise
                duration = time.time() - start_time

            # record_binance_api_call("get_account", "success", duration)
            # binance_connection_status.set(1)

            logger.info("✅ Cliente de Binance inicializado correctamente")
            if not self.simulation_mode:
                logger.info(
                    f"   Tipo de cuenta: {account_info.get('accountType', 'N/A')}"
                )

        except BinanceAPIException as e:
            if e.code == -1022:
                logger.error(f"❌ Error de autenticación Binance (1022): {e.message}")
                if self.force_real_mode:
                    # En modo forzado, propagar el error para que falle visiblemente
                    raise
                logger.warning(
                    "🔧 Activando modo simulación debido a credenciales inválidas"
                )
                self.simulation_mode = True
                # binance_connection_status.set(0)
            else:
                logger.error(f"❌ Error de Binance API: {e}")
                if self.force_real_mode:
                    raise
                self.simulation_mode = True
                # binance_connection_status.set(0)

        except Exception as e:
            logger.error(f"❌ Error inesperado inicializando Binance: {e}")
            if self.force_real_mode:
                raise
            self.simulation_mode = True
            # binance_connection_status.set(0)

    def get_account_info(self) -> Dict[str, Any]:
        """Obtiene información de la cuenta"""
        if self.simulation_mode and not self.force_real_mode:
            logger.info("🔄 Modo simulación: Retornando datos simulados de cuenta")
            return self._get_simulated_account_info()

        try:
            start_time = time.time()

            # Reintentos con backoff para robustez
            @tenacity.retry(
                wait=tenacity.wait_exponential(max=8),
                stop=tenacity.stop_after_attempt(4),
                reraise=True,
            )
            def _get_account():
                return self.client.get_account(recvWindow=10000)

            account_info = _get_account()
            duration = time.time() - start_time

            # record_binance_api_call("get_account", "success", duration)
            return account_info

        except BinanceAPIException as e:
            # record_binance_api_call("get_account", f"error_{e.code}", 0)
            logger.error(f"Error obteniendo información de cuenta: {e}")
            raise

    def get_account(self) -> Dict[str, Any]:
        """Alias para get_account_info para compatibilidad"""
        return self.get_account_info()

    def get_balance(self, asset: str) -> Dict[str, Any]:
        """Obtiene el balance de un activo específico"""
        if self.simulation_mode and not self.force_real_mode:
            logger.info(f"🔄 Modo simulación: Retornando balance simulado para {asset}")
            return self._get_simulated_balance(asset)

        try:
            start_time = time.time()

            @tenacity.retry(
                wait=tenacity.wait_exponential(max=8),
                stop=tenacity.stop_after_attempt(4),
                reraise=True,
            )
            def _get_balance():
                return self.client.get_asset_balance(asset=asset)

            balance = _get_balance()
            duration = time.time() - start_time

            # record_binance_api_call("get_asset_balance", "success", duration)
            return balance

        except BinanceAPIException as e:
            # record_binance_api_call("get_asset_balance", f"error_{e.code}", 0)
            logger.error(f"Error obteniendo balance de {asset}: {e}")
            raise

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Obtiene información detallada de un símbolo incluyendo stepSize y minQty"""
        try:
            if symbol not in self._symbol_info_cache:
                exchange_info = self.client.get_exchange_info()
                for s in exchange_info["symbols"]:
                    if s["symbol"] == symbol.upper():
                        # Extraer filtros importantes
                        filters = {f["filterType"]: f for f in s["filters"]}
                        self._symbol_info_cache[symbol] = {
                            "symbol": s["symbol"],
                            "baseAsset": s["baseAsset"],
                            "quoteAsset": s["quoteAsset"],
                            "stepSize": float(
                                filters.get("LOT_SIZE", {}).get("stepSize", "0.001")
                            ),
                            "minQty": float(
                                filters.get("LOT_SIZE", {}).get("minQty", "0.001")
                            ),
                            "minNotional": float(
                                filters.get("MIN_NOTIONAL", {}).get(
                                    "minNotional", "5.0"
                                )
                            ),
                            "pricePrecision": s["quotePrecision"],
                            "quantityPrecision": s["baseAssetPrecision"],
                        }
                        break
            return self._symbol_info_cache.get(symbol)
        except Exception as e:
            logging.error(f"Error obteniendo información del símbolo {symbol}: {e}")
            return None

    def adjust_quantity_precision(self, quantity: float, symbol: str) -> Dict[str, Any]:
        """Ajusta la cantidad a la precisión requerida por Binance y retorna información detallada"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                # Fallback a valores por defecto
                step_size = 0.001
                min_qty = 0.001
                min_notional = 5.0
            else:
                step_size = symbol_info["stepSize"]
                min_qty = symbol_info["minQty"]
                min_notional = symbol_info["minNotional"]

            # Ajustar a la precisión requerida
            adjusted_quantity = math.floor(quantity / step_size) * step_size

            # Asegurar que no sea menor que el mínimo
            if adjusted_quantity < min_qty:
                adjusted_quantity = min_qty

            # Redondear a la precisión correcta
            precision = int(-math.log10(step_size))
            adjusted_quantity = round(adjusted_quantity, precision)

            return {
                "original_quantity": quantity,
                "adjusted_quantity": adjusted_quantity,
                "step_size": step_size,
                "min_qty": min_qty,
                "min_notional": min_notional,
                "precision": precision,
                "symbol_info": symbol_info,
            }
        except Exception as e:
            logging.error(f"Error ajustando precisión de cantidad: {e}")
            return {
                "original_quantity": quantity,
                "adjusted_quantity": quantity,
                "step_size": 0.001,
                "min_qty": 0.001,
                "min_notional": 5.0,
                "precision": 3,
                "symbol_info": None,
                "error": str(e),
            }

    def validate_order_parameters(
        self, symbol: str, quantity: float, side: str, order_type: str = "MARKET"
    ) -> Dict[str, Any]:
        """Valida los parámetros de una orden antes de ejecutarla incluyendo comisiones"""
        try:
            # Ajustar cantidad
            quantity_info = self.adjust_quantity_precision(quantity, symbol)

            # Obtener precio actual para validaciones
            current_price = self.get_current_price(symbol)

            # Calcular valor notional con Decimal para precisión
            q = Decimal(str(quantity_info["adjusted_quantity"]))
            p = Decimal(str(current_price))
            notional_value = float(q * p)

            # Calcular comisión (internamente puede usar Decimal)
            commission = commission_manager.calculate_commission(
                notional_value, order_type, symbol
            )

            # Validaciones
            errors = []
            warnings = []

            if quantity_info["adjusted_quantity"] < quantity_info["min_qty"]:
                errors.append(
                    f"Cantidad {quantity_info['adjusted_quantity']} es menor al mínimo {quantity_info['min_qty']}"
                )

            if notional_value < quantity_info["min_notional"]:
                errors.append(
                    f"Valor notional ${notional_value:.2f} es menor al mínimo ${quantity_info['min_notional']}"
                )

            if quantity_info["original_quantity"] != quantity_info["adjusted_quantity"]:
                warnings.append(
                    f"Cantidad ajustada de {quantity_info['original_quantity']} a {quantity_info['adjusted_quantity']} por precisión"
                )

            # Validación de comisión
            commission_percentage = (
                (commission / notional_value * 100) if notional_value > 0 else 0
            )
            if commission_percentage > 1.0:  # Si la comisión es más del 1%
                warnings.append(
                    f"Comisión alta: {commission_percentage:.2f}% (${commission:.6f} USDT)"
                )

            return {
                "is_valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "quantity_info": quantity_info,
                "current_price": current_price,
                "notional_value": notional_value,
                "commission_usdt": commission,
                "commission_percentage": commission_percentage,
                "recommended_quantity": quantity_info["adjusted_quantity"],
            }
        except Exception as e:
            logging.error(f"Error validando parámetros de orden: {e}")
            return {
                "is_valid": False,
                "errors": [f"Error en validación: {e}"],
                "warnings": [],
                "quantity_info": None,
                "current_price": None,
                "notional_value": None,
                "commission_usdt": None,
                "commission_percentage": None,
                "recommended_quantity": None,
            }

    def get_current_price(self, symbol: str) -> float:
        """Obtiene el precio actual de un símbolo"""
        if self.simulation_mode and not self.force_real_mode:
            logger.info(f"🔄 Modo simulación: Retornando precio simulado para {symbol}")
            return self._get_simulated_price(symbol)

        try:
            start_time = time.time()

            @tenacity.retry(
                wait=tenacity.wait_exponential(max=8),
                stop=tenacity.stop_after_attempt(4),
                reraise=True,
            )
            def _get_ticker():
                return self.client.get_symbol_ticker(symbol=symbol.upper())

            ticker = _get_ticker()
            duration = time.time() - start_time

            # record_binance_api_call("get_symbol_ticker", "success", duration)
            return float(ticker["price"])

        except BinanceAPIException as e:
            # record_binance_api_call("get_symbol_ticker", f"error_{e.code}", 0)
            logger.error(f"Error obteniendo precio de {symbol}: {e}")
            raise

    def execute_trading_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Coloca una orden en Binance con cálculo de comisiones"""
        if self.simulation_mode and not self.force_real_mode:
            logger.info(
                f"🔄 Modo simulación: Simulando orden {side} {quantity} {symbol} @ {price}"
            )
            return self._simulate_order(symbol, side, order_type, quantity, price)

        try:
            start_time = time.time()

            # Calcular comisión antes de ejecutar la orden
            current_price = price if price else self.get_current_price(symbol)
            # Precisión monetaria con Decimal
            qd = Decimal(str(quantity))
            pd = Decimal(str(current_price))
            notional_value = float(qd * pd)
            commission = commission_manager.calculate_commission(
                notional_value, order_type, symbol
            )

            logger.info(
                f"💰 Comisión calculada para {side} {quantity} {symbol}: ${commission:.6f} USDT"
            )

            # Preparar cantidad formateada evitando notación científica y respetando stepSize
            def _format_quantity(sym: str, qty: float) -> str:
                info = self.get_symbol_info(sym) or {}
                step = Decimal(str(info.get("stepSize", "0.00000001")))
                getcontext().prec = 28
                q = Decimal(str(qty))
                units = (q / step).to_integral_value(rounding=ROUND_DOWN)
                q_adj = units * step
                precision = max(0, -step.as_tuple().exponent)
                return f"{q_adj:.{precision}f}"

            qty_str = _format_quantity(symbol, quantity)

            if order_type == "MARKET":
                if side == "BUY":
                    order = self.client.order_market_buy(
                        symbol=symbol, quantity=qty_str
                    )
                else:
                    order = self.client.order_market_sell(
                        symbol=symbol, quantity=qty_str
                    )
            else:  # LIMIT
                if side == "BUY":
                    order = self.client.order_limit_buy(
                        symbol=symbol, quantity=qty_str, price=str(price)
                    )
                else:
                    order = self.client.order_limit_sell(
                        symbol=symbol, quantity=qty_str, price=str(price)
                    )

            duration = time.time() - start_time
            # record_binance_api_call("execute_trading_order", "success", duration)

            # Agregar información de comisión al resultado
            order["commission_info"] = {
                "commission_usdt": commission,
                "commission_rate": commission / notional_value
                if notional_value > 0
                else 0,
                "notional_value": notional_value,
                "order_type": order_type,
            }

            logger.info(
                f"✅ Orden colocada exitosamente: {order['orderId']} - Comisión: ${commission:.6f} USDT"
            )
            return order

        except BinanceAPIException as e:
            # record_binance_api_call("execute_trading_order", f"error_{e.code}", 0)
            logger.error(f"Error colocando orden: {e}")
            raise

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene órdenes abiertas"""
        if self.simulation_mode and not self.force_real_mode:
            logger.info("🔄 Modo simulación: Retornando órdenes simuladas")
            return self._get_simulated_open_orders(symbol)

        try:
            start_time = time.time()

            @tenacity.retry(
                wait=tenacity.wait_exponential(max=8),
                stop=tenacity.stop_after_attempt(4),
                reraise=True,
            )
            def _get_open_orders():
                return self.client.get_open_orders(symbol=symbol)

            orders = _get_open_orders()
            duration = time.time() - start_time

            # record_binance_api_call("get_open_orders", "success", duration)
            return orders

        except BinanceAPIException as e:
            # record_binance_api_call("get_open_orders", f"error_{e.code}", 0)
            logger.error(f"Error obteniendo órdenes abiertas: {e}")
            raise

    def validate_grid_profitability(
        self,
        symbol: str,
        min_price: float,
        max_price: float,
        quantity: float,
        num_levels: int,
        min_profit_percentage: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Valida la rentabilidad de una estrategia de grid trading considerando comisiones

        Args:
            symbol: Símbolo del par
            min_price: Precio mínimo del grid
            max_price: Precio máximo del grid
            quantity: Cantidad por nivel
            num_levels: Número de niveles
            min_profit_percentage: Porcentaje mínimo de ganancia requerido

        Returns:
            Dict con análisis de rentabilidad
        """
        try:
            # Obtener análisis de grid ajustado para comisiones
            grid_analysis = commission_manager.adjust_grid_levels_for_commissions(
                min_price,
                max_price,
                num_levels,
                quantity,
                min_profit_percentage,
                "MARKET",
                symbol,
            )

            # Calcular estadísticas
            profitable_levels = sum(
                1
                for level in grid_analysis["profitability_analysis"]
                if level["is_profitable"]
            )
            total_levels = len(grid_analysis["profitability_analysis"])
            profitability_rate = (
                (profitable_levels / total_levels * 100) if total_levels > 0 else 0
            )

            # Calcular ganancia total estimada
            total_net_profit = sum(
                level["net_profit"] for level in grid_analysis["profitability_analysis"]
            )
            total_commission = grid_analysis["commission_per_trade"] * total_levels

            return {
                "is_profitable": profitability_rate
                >= 80,  # Al menos 80% de niveles rentables
                "profitability_rate": profitability_rate,
                "profitable_levels": profitable_levels,
                "total_levels": total_levels,
                "total_net_profit": total_net_profit,
                "total_commission": total_commission,
                "commission_per_trade": grid_analysis["commission_per_trade"],
                "adjusted_levels": grid_analysis["adjusted_levels"],
                "profitability_analysis": grid_analysis["profitability_analysis"],
                "recommendation": "PROCEED"
                if profitability_rate >= 80
                else "ADJUST_PARAMETERS",
            }

        except Exception as e:
            logger.error(f"Error validando rentabilidad de grid: {e}")
            return {"is_profitable": False, "error": str(e), "recommendation": "ERROR"}

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancela una orden"""
        if self.simulation_mode and not self.force_real_mode:
            logger.info(
                f"🔄 Modo simulación: Simulando cancelación de orden {order_id}"
            )
            return self._simulate_cancel_order(symbol, order_id)

        try:
            start_time = time.time()
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            duration = time.time() - start_time

            # record_binance_api_call("cancel_order", "success", duration)
            return result

        except BinanceAPIException as e:
            # record_binance_api_call("cancel_order", f"error_{e.code}", 0)
            logger.error(f"Error cancelando orden: {e}")
            raise

    def is_simulation_mode(self) -> bool:
        """Retorna si está en modo simulación"""
        return self.simulation_mode

    # ============================================================================
    # MÉTODOS DE SIMULACIÓN
    # ============================================================================

    def _get_simulated_account_info(self) -> Dict[str, Any]:
        """Retorna información simulada de cuenta"""
        return {
            "accountType": "SPOT",
            "makerCommission": 15,
            "takerCommission": 15,
            "buyerCommission": 0,
            "sellerCommission": 0,
            "canTrade": True,
            "canWithdraw": True,
            "canDeposit": True,
            "updateTime": int(time.time() * 1000),
            "balances": [
                {"asset": "USDT", "free": "1000.0", "locked": "0.0"},
                {"asset": "BTC", "free": "0.01", "locked": "0.0"},
                {"asset": "ETH", "free": "0.1", "locked": "0.0"},
            ],
        }

    def _get_simulated_balance(self, asset: str) -> Dict[str, Any]:
        """Retorna balance simulado"""
        balances = {
            "USDT": {"free": "1000.0", "locked": "0.0"},
            "BTC": {"free": "0.01", "locked": "0.0"},
            "ETH": {"free": "0.1", "locked": "0.0"},
        }

        return {
            "asset": asset,
            "free": balances.get(asset, "0.0")["free"],
            "locked": balances.get(asset, "0.0")["locked"],
        }

    def _get_simulated_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Retorna información simulada de símbolo"""
        return {
            "symbol": symbol,
            "status": "TRADING",
            "baseAsset": symbol.replace("USDT", ""),
            "quoteAsset": "USDT",
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00001",
                    "maxQty": "100000.00000000",
                    "stepSize": "0.00001",
                },
                {"filterType": "MIN_NOTIONAL", "minNotional": "10.00000000"},
            ],
        }

    def _get_simulated_price(self, symbol: str) -> float:
        """Retorna precio simulado"""
        prices = {"BTCUSDT": 50000.0, "ETHUSDT": 3000.0, "ADAUSDT": 0.5, "DOTUSDT": 7.0}
        return prices.get(symbol, 100.0)

    def _simulate_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Simula una orden"""
        order_id = int(time.time() * 1000)

        return {
            "orderId": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),
            "price": str(price) if price else "0",
            "status": "FILLED",
            "timeInForce": "GTC",
            "time": int(time.time() * 1000),
            "updateTime": int(time.time() * 1000),
            "isWorking": False,
        }

    def _get_simulated_open_orders(
        self, symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retorna órdenes abiertas simuladas"""
        return []

    def _simulate_cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Simula cancelación de orden"""
        return {
            "orderId": order_id,
            "symbol": symbol,
            "status": "CANCELED",
            "clientOrderId": "simulated",
            "price": "0",
            "origQty": "0",
            "executedQty": "0",
            "cummulativeQuoteQty": "0",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY",
        }

    # ============================================================================
    # MÉTODOS OPTIMIZADOS CON CACHE REDIS
    # ============================================================================

    async def get_account_optimized(self) -> Dict[str, Any]:
        """
        Obtener información de cuenta con cache Redis para reducir latencia

        Returns:
            Información de cuenta optimizada
        """
        try:
            # Intentar obtener desde cache primero
            cached_account = await self.redis_cache.get_account_info()
            if cached_account:
                logger.debug("📦 Account info obtenido desde cache Redis")
                return cached_account

            # Si no está en cache, obtener de Binance
            start_time = time.time()

            if self.simulation_mode:
                account_info = self._get_simulated_account_info()
            else:
                account_info = self.get_account()

            duration = time.time() - start_time
            logger.info(f"⏱️ Account info obtenido de Binance en {duration:.3f}s")

            # Guardar en cache
            await self.redis_cache.set_account_info(account_info)

            return account_info

        except Exception as e:
            logger.error(f"Error obteniendo account info optimizado: {e}")
            # Fallback a método original
            return self.get_account()

    async def get_symbol_ticker_optimized(self, symbol: str) -> Dict[str, Any]:
        """
        Obtener ticker de símbolo con cache Redis

        Args:
            symbol: Símbolo a consultar

        Returns:
            Ticker optimizado
        """
        try:
            # Intentar obtener desde cache
            cached_ticker = await self.redis_cache.get_symbol_ticker(symbol)
            if cached_ticker:
                logger.debug(f"📦 Ticker {symbol} obtenido desde cache Redis")
                return cached_ticker

            # Obtener de Binance
            start_time = time.time()

            if self.simulation_mode:
                price = self._get_simulated_price(symbol)
                ticker = {
                    "symbol": symbol,
                    "price": str(price),
                    "time": int(time.time() * 1000),
                }
            else:
                ticker = self.client.get_symbol_ticker(symbol=symbol)

            duration = time.time() - start_time
            logger.debug(f"⏱️ Ticker {symbol} obtenido de Binance en {duration:.3f}s")

            # Guardar en cache
            await self.redis_cache.set_symbol_ticker(symbol, ticker)

            return ticker

        except Exception as e:
            logger.error(f"Error obteniendo ticker optimizado {symbol}: {e}")
            # Fallback a método original
            return self.get_symbol_ticker(symbol)

    async def get_exchange_info_optimized(self, symbol: str = None) -> Dict[str, Any]:
        """
        Obtener información del exchange con cache Redis

        Args:
            symbol: Símbolo específico (opcional)

        Returns:
            Información del exchange optimizada
        """
        try:
            # Intentar obtener desde cache
            cached_info = await self.redis_cache.get_exchange_info(symbol)
            if cached_info:
                logger.debug("📦 Exchange info obtenido desde cache Redis")
                return cached_info

            # Obtener de Binance
            start_time = time.time()

            if self.simulation_mode:
                exchange_info = self._get_simulated_exchange_info()
            else:
                exchange_info = self.client.get_exchange_info()

            duration = time.time() - start_time
            logger.info(f"⏱️ Exchange info obtenido de Binance en {duration:.3f}s")

            # Guardar en cache
            await self.redis_cache.set_exchange_info(exchange_info, symbol)

            return exchange_info

        except Exception as e:
            logger.error(f"Error obteniendo exchange info optimizado: {e}")
            # Fallback a método original
            return self.get_exchange_info()

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache Redis"""
        return await self.redis_cache.get_cache_stats()

    async def invalidate_symbol_cache(self, symbol: str):
        """Invalidar cache de un símbolo específico"""
        await self.redis_cache.invalidate_symbol(symbol)
        logger.info(f"🗑️ Cache invalidado para {symbol}")
