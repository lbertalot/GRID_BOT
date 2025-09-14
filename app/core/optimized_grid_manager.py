"""
Optimized Grid Manager for Multi-Asset Trading
Following FastAPI best practices and .cursorrules
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_DOWN, getcontext
from dataclasses import dataclass
from datetime import datetime
import json
import os
import asyncpg
import math

import requests
from pydantic import BaseModel, Field
from pydantic import field_validator, model_validator
from binance import Client
from dotenv import load_dotenv

# Importar configuración de SQLAlchemy ANTES de cualquier import de SQLAlchemy
from app.core.sqlalchemy_logging import configure_sqlalchemy_logging
configure_sqlalchemy_logging()

# Cargar variables de entorno desde .env
load_dotenv()

from app.services.telegram_alert import send_telegram_alert
from app.services.grid_strategy import decide_grid_action, calculate_grid_levels
from app.services.order_validation import OrderValidator
from app.models.asset_limit import AssetLimit
from app.services.risk_manager import risk_manager, RiskStatus
from app.services.metrics_service import metrics_service
from app.services.strategy_manager import strategy_manager
from app.services.binance_async import AsyncBinanceWrapper
from app.services.commission_manager import commission_manager

# Configurar logging optimizado
from app.core.optimized_logging import setup_optimized_logging
logger = setup_optimized_logging()

class AssetConfig(BaseModel):
    symbol: str
    min_price: float
    max_price: float
    grids: int
    quantity: float
    is_active: bool = True
    last_action: Optional[str] = None
    grid_levels: List[float] = Field(default_factory=list)

    @field_validator('grid_levels')
    @classmethod
    def calculate_grid_levels_on_init(cls, v, info):
        if v:
            return v
        data = info.data or {}
        return calculate_grid_levels(
            data.get('min_price'),
            data.get('max_price'),
            data.get('grids')
        )

    @model_validator(mode='after')
    def ensure_grid_levels(self):
        # Garantiza niveles de grilla calculados si no vienen en el JSON
        if (not self.grid_levels) and self.min_price and self.max_price and self.grids:
            self.grid_levels = calculate_grid_levels(self.min_price, self.max_price, self.grids)
        return self


class GridManagerConfig(BaseModel):
    """Pydantic model for grid manager configuration"""
    assets: Dict[str, AssetConfig] = Field(default_factory=dict)
    update_interval: int = Field(default=60, ge=30, le=300)
    min_notional_threshold: float = Field(default=10.0, ge=1.0)  # Cambiado a 10.0 por defecto
    max_concurrent_orders: int = Field(default=3, ge=1, le=10)


@dataclass
class TradingResult:
    timestamp: datetime
    symbol: str
    action: str
    quantity: float
    price: float
    order_id: str
    status: str
    profit: float = None


class OptimizedGridManager:
    """
    Optimized Grid Manager following functional programming principles
    and FastAPI best practices
    """
    
    def __init__(self, config: GridManagerConfig):
        self.config = config
        self.client = self._initialize_binance_client()
        self.order_validator = OrderValidator(self.client)
        self.trading_history: List[TradingResult] = []
        self.asset_limits: Dict[str, AssetLimit] = {}
        self.insufficient_funds: Dict[str, Dict] = {} # Nuevo: para registrar activos con saldo insuficiente
        self.config_file_path: Optional[str] = None  # Para recargar configuración
        # Wrapper asíncrono con caché y rate limiting para evitar bloqueos
        self.async_binance = AsyncBinanceWrapper(
            ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "5")),
            rate_per_sec=float(os.getenv("BINANCE_RATE_PER_SEC", "5")),
            burst=int(os.getenv("BINANCE_RATE_BURST", "10"))
        )
        
    async def _load_asset_limits(self):
        """Load asset trading limits from the database."""
        database_url = os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot")
        conn = None
        try:
            conn = await asyncpg.connect(database_url)
            rows = await conn.fetch("SELECT * FROM asset_limits")
            for row in rows:
                self.asset_limits[row['symbol']] = AssetLimit(**dict(row))
            logger.info(f"Cargados {len(self.asset_limits)} límites de activos desde la base de datos.")
        except Exception as e:
            logger.error(f"Error cargando límites de activos desde la BD: {e}")
        finally:
            if conn:
                await conn.close()

    def _initialize_binance_client(self) -> Client:
        """Initialize Binance client using Singleton pattern"""
        try:
            from app.services.binance_client_singleton import binance_client_singleton
            
            logger.info("🔧 Inicializando cliente Binance usando Singleton")
            client = binance_client_singleton.client
            
            if not client:
                raise Exception("No se pudo obtener cliente de Binance desde Singleton")
            
            # Verificar credenciales
            if not hasattr(client, 'api_key') or not client.api_key:
                logger.error("❌ Cliente de Binance sin credenciales válidas")
                raise Exception("Cliente de Binance sin credenciales válidas")
            
            logger.info(f"✅ Cliente Binance Singleton inicializado correctamente - API Key: {client.api_key[:10]}...")
            
            # Obtener información de cuenta para uso posterior
            try:
                account_info = binance_client_singleton.get_account_info()
                self._account_info = account_info
                self._account_type = account_info.get('accountType', 'SPOT')
                logger.info(f"✅ Información de cuenta obtenida: {len(account_info.get('balances', []))} balances")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo obtener información de cuenta: {e}")
                self._account_info = {}
                self._account_type = 'N/A'
            
            return client
            
        except Exception as e:
            logger.error(f"❌ Error inicializando cliente Binance Singleton: {e}")
            return None

    async def get_asset_balances(self) -> Dict[str, float]:
        """Get current asset balances from Binance with robust error handling"""
        try:
            if not self.client:
                logger.error("❌ Cliente de Binance no inicializado")
                return {}
            
            # Verificar que el cliente tenga credenciales válidas
            if not hasattr(self.client, 'api_key') or not self.client.api_key:
                logger.error("❌ Cliente de Binance sin credenciales válidas")
                return {}
            
            logger.info(f"✅ Cliente de Binance verificado - API Key: {self.client.api_key[:10]}...")
            
            logger.info("🔄 Obteniendo información de cuenta de Binance...")
            
            # Usar información de cuenta ya verificada si está disponible
            if hasattr(self, '_account_info') and self._account_info:
                account_info = self._account_info
                logger.info("✅ Usando información de cuenta pre-verificada")
            else:
                # Obtener información de cuenta con manejo robusto de errores
                from binance.exceptions import BinanceAPIException, BinanceRequestException
                
                try:
                    # Evitar bloqueo en loop async
                    account_info = await asyncio.to_thread(self.client.get_account)
                except BinanceAPIException as e:
                    if e.code == -2015:
                        logger.error("❌ API Secret required for private endpoints")
                        logger.error("   Verifica que las credenciales sean correctas")
                        return {}
                    elif e.code == -2013:
                        logger.error("❌ Invalid API-key")
                        return {}
                    else:
                        logger.error(f"❌ Error de API de Binance: {e}")
                        return {}
                except BinanceRequestException as e:
                    logger.error(f"❌ Error de conexión con Binance: {e}")
                    return {}
                except Exception as e:
                    logger.error(f"❌ Error inesperado obteniendo información de cuenta: {e}")
                    return {}
            
            logger.info(f"✅ Información de cuenta obtenida: {len(account_info.get('balances', []))} balances")
            
            balances = {}
            for balance in account_info['balances']:
                asset = balance['asset']
                free_balance = float(balance['free'])
                if free_balance > 0:
                    balances[asset] = free_balance
                    logger.info(f"💰 Balance {asset}: {free_balance}")
            
            logger.info(f"📊 Total de activos con saldo: {len(balances)}")
            return balances
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo balances: {e}")
            return {}

    async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for given symbols"""
        try:
            if not self.client:
                return {}
            
            # Filtrar símbolos válidos (excluir metadatos)
            valid_symbols = [s for s in symbols if not s.startswith('_')]
            
            # Consultas concurrentes con caché/TTL para minimizar latencia y presión a la API
            results: Dict[str, float] = {}
            async def _fetch(sym: str):
                try:
                    price = await self.async_binance.get_price(sym)
                except Exception as e:
                    logger.warning(f"Error obteniendo precio para {sym}: {e}")
                    price = 0.0
                results[sym] = price

            await asyncio.gather(*[_fetch(s) for s in valid_symbols])
            return results
        except Exception as e:
            logger.error(f"Error obteniendo precios: {e}")
            return {}

    def calculate_optimal_quantities(self, balances: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
        """Calcula las cantidades óptimas para operar, usando la configuración del archivo."""
        optimal_quantities = {}
        self.insufficient_funds = {}
        
        for symbol, asset_config in self.config.assets.items():
            if not asset_config.is_active:
                continue
                
            base_asset = symbol.replace("USDT", "")
            current_balance = balances.get(base_asset, 0)
            current_price = prices.get(symbol, 0)
            
            if current_price <= 0:
                continue
            
            # Usar la cantidad configurada en el archivo
            quantity_to_use = asset_config.quantity
            
            # Verificar que cumple con min_notional del sistema y del exchange
            min_notional = self.config.min_notional_threshold
            try:
                limits = self.asset_limits.get(symbol)
                if limits and getattr(limits, 'min_notional', None):
                    min_notional = max(min_notional, float(limits.min_notional))
            except Exception:
                pass
            notional_value = quantity_to_use * current_price
            
            if notional_value < min_notional:
                logger.warning(f"La cantidad configurada para {symbol} no cumple min_notional. "
                             f"Valor: {notional_value:.4f}, Mínimo: {min_notional}")
                # Calcular cantidad mínima requerida
                min_quantity = min_notional / current_price
                quantity_to_use = min_quantity
            
            # Ajustar a step_size si corresponde
            limits = self.asset_limits.get(symbol)
            if limits and getattr(limits, 'step_size', None):
                step_size = limits.step_size
                precision = int(round(-math.log(step_size, 10), 0))
                quantity_to_use = float(f"{math.floor(quantity_to_use / step_size) * step_size:.{precision}f}")
            
            # Log detallado del saldo y mínimos requeridos
            logger.info(f"[{symbol}] Saldo {base_asset} disponible: {current_balance}, cantidad requerida: {quantity_to_use}")
            logger.info(f"[{symbol}] Valor nocional: {notional_value:.4f} USDT, mínimo requerido: {min_notional} USDT")
            
            if current_balance >= quantity_to_use:
                optimal_quantities[symbol] = quantity_to_use
                logger.info(f"✅ [{symbol}] Saldo suficiente para operar")
            else:
                missing = max(0, quantity_to_use - current_balance)
                self.insufficient_funds[symbol] = {
                    "saldo_actual": current_balance,
                    "cantidad_necesaria": quantity_to_use,
                    "faltante": missing,
                    "min_notional": min_notional,
                    "precio_actual": current_price
                }
                logger.warning(f"⛔ [{symbol}] Saldo insuficiente - Faltan {missing} {base_asset}")
        
        return optimal_quantities

    def _adjust_quantity_to_step_size(self, symbol: str, quantity: float) -> float:
        """Adjusts the order quantity to match the symbol's step size."""
        limits = self.asset_limits.get(symbol)
        if not limits or not limits.step_size:
            return quantity
        
        step_size = limits.step_size
        precision = int(round(-math.log(step_size, 10), 0))
        return float(f"{math.floor(quantity / step_size) * step_size:.{precision}f}")

    async def execute_grid_trading_cycle(self) -> List[TradingResult]:
        """
        Execute a complete grid trading cycle for all configured assets
        """
        try:
            from time import perf_counter
            from app.core.metrics import trading_metrics
            cycle_start = perf_counter()
            # Verificar límites de riesgo antes de ejecutar trading
            # Comentado temporalmente para evitar errores
            # risk_status = await risk_manager.check_portfolio_risk()
            # 
            # if risk_status == RiskStatus.STOP_TRADING:
            #     logger.warning("Trading detenido por límites de riesgo críticos")
            #     send_telegram_alert("🚨 Trading detenido por límites de riesgo críticos")
            #     return []
            # 
            # if risk_status == RiskStatus.DANGER:
            #     logger.warning("Trading en modo de riesgo alto - ejecutando con precaución")
            #     send_telegram_alert("⚠️ Trading en modo de riesgo alto - ejecutando con precaución")
            # 
            # # Verificar si el trading está habilitado
            # if not risk_manager.trading_enabled:
            #     logger.info("Trading deshabilitado por gestión de riesgos")
            #     return []
            
            logger.info("Iniciando ciclo de trading con verificación de riesgos...")
            
            # Verificar y ejecutar rebalanceo automático si es necesario
            try:
                from app.services.auto_rebalancer import auto_rebalancer
                rebalance_status = await auto_rebalancer.get_rebalance_status()
                
                if rebalance_status.get('assets_needing_rebalance', 0) > 0:
                    logger.info(f"🔄 Detectados {rebalance_status['assets_needing_rebalance']} activos que necesitan rebalanceo")
                    
                    if rebalance_status.get('can_rebalance', False):
                        logger.info("✅ Ejecutando rebalanceo automático...")
                        rebalance_result = await auto_rebalancer.check_and_rebalance()
                        logger.info(f"Rebalanceo completado: {rebalance_result.get('status')}")
                    else:
                        logger.warning(f"⚠️ No se puede rebalancear - USDT insuficiente")
                        logger.warning(f"   Necesario: ${rebalance_status.get('total_needed_usdt', 0):.2f}")
                        logger.warning(f"   Disponible: ${rebalance_status.get('available_usdt', 0):.2f}")
                else:
                    logger.info("✅ Todos los activos tienen saldo suficiente")
                    
            except Exception as e:
                logger.error(f"Error en rebalanceo automático: {e}")
            
            balances = await self.get_asset_balances()
            symbols = [asset.symbol for asset in self.config.assets.values() if asset.is_active]
            prices = await self.get_current_prices(symbols)
            # Adaptación de estrategia (no bloquea, usa colector async)
            try:
                changes = await strategy_manager.adapt_manager(self, symbols)
                if changes:
                    logger.info(f"🧠 Adaptación aplicada por StrategyManager: {changes}")
            except Exception as e:
                logger.warning(f"No se pudo adaptar estrategia en este ciclo: {e}")
            optimal_quantities = self.calculate_optimal_quantities(balances, prices)
            trading_results = []
            
            logger.info(f"📊 Evaluando {len(symbols)} símbolos activos para trading")
            logger.info(f"💰 Balances disponibles: {len(balances)} activos con saldo")
            logger.info(f"📈 Precios obtenidos: {len(prices)} símbolos")
            logger.info(f"🎯 Cantidades óptimas calculadas: {len(optimal_quantities)} símbolos")
            
            for symbol, quantity in optimal_quantities.items():
                asset_config = self.config.assets.get(symbol)
                if not asset_config:
                    logger.warning(f"⛔ {symbol}: Configuración de activo no encontrada")
                    continue
                
                logger.info(f"🔍 Evaluando {symbol} para trading...")
                
                # Verificar riesgo específico del activo
                # Comentado temporalmente para evitar errores
                # asset_risk_status = await risk_manager.check_asset_risk(symbol)
                # if asset_risk_status == RiskStatus.STOP_TRADING:
                #     logger.warning(f"Trading detenido para {symbol} por riesgo crítico")
                #     continue
                # 
                # if asset_risk_status == RiskStatus.DANGER:
                #     # Ejecutar stop-loss si es necesario
                #     await risk_manager.execute_stop_loss(symbol)
                #     logger.warning(f"Stop-loss ejecutado para {symbol}")
                #     continue
                    
                current_price = prices.get(symbol, 0)
                if current_price <= 0:
                    logger.warning(f"⛔ {symbol}: Precio es 0 o negativo (${current_price}), saltando operación.")
                    continue
                
                logger.info(f"📊 {symbol}: Precio actual ${current_price}, cantidad óptima {quantity}")
                
                action = decide_grid_action(prices.get(symbol, 0), asset_config.grid_levels, asset_config.last_action)
                
                if action and action.get("action"):
                    logger.info(f"✅ {symbol}: Señal de {action['action']} detectada en nivel {action.get('level', 'N/A')}")
                    
                    # Usar la cantidad calculada (que ya incluye validaciones)
                    quantity_to_use = quantity
                    
                    # Validar saldo
                    base_asset = symbol.replace("USDT", "")
                    available_balance = balances.get(base_asset, 0)
                    
                    # Validar requisitos de fondos usando FundManager
                    from app.services.fund_manager import fund_manager
                    
                    is_valid, message, details = await fund_manager.validate_trade_requirements(
                        symbol=symbol,
                        side=action["action"],
                        quantity=quantity_to_use,
                        price=current_price,
                        balances=balances
                    )
                    
                    if not is_valid:
                        # Log más detallado para debugging
                        logger.info(f"🔍 {symbol}: Validación fallida - {message}")
                        logger.info(f"   📊 Detalles: {details}")
                        
                        # Intentar con cantidad reducida si es posible
                        if "shortage" in details:
                            shortage = details.get("shortage", 0)
                            if shortage > 0:
                                # Calcular cantidad ajustada
                                adjusted_quantity = quantity_to_use * 0.8  # Reducir 20%
                                logger.info(f"🔄 {symbol}: Intentando con cantidad ajustada: {adjusted_quantity}")
                                
                                # Validar con cantidad ajustada
                                is_valid_adj, message_adj, details_adj = await fund_manager.validate_trade_requirements(
                                    symbol=symbol,
                                    side=action["action"],
                                    quantity=adjusted_quantity,
                                    price=current_price,
                                    balances=balances
                                )
                                
                                if is_valid_adj:
                                    quantity_to_use = adjusted_quantity
                                    logger.info(f"✅ {symbol}: Validación exitosa con cantidad ajustada")
                                else:
                                    logger.warning(f"⛔ {symbol}: No se puede ajustar cantidad - {message_adj}")
                                    continue
                            else:
                                logger.warning(f"⛔ {symbol}: {message}")
                                continue
                        else:
                            logger.warning(f"⛔ {symbol}: {message}")
                            continue
                    
                    # Usar cantidad ajustada si es necesario
                    adjusted_quantity = details.get("quantity", quantity_to_use)
                    if adjusted_quantity and adjusted_quantity != quantity_to_use:
                        logger.info(f"🔄 {symbol}: Ajustando cantidad de {quantity_to_use} a {adjusted_quantity}")
                        quantity_to_use = adjusted_quantity
                        
                        # Verificar min_notional
                        notional_value = quantity_to_use * current_price
                        min_notional = self.config.min_notional_threshold
                        
                        if notional_value < min_notional:
                            logger.warning(f"⛔ {symbol}: Valor nocional insuficiente. Valor: ${notional_value:.4f}, Mínimo: ${min_notional}")
                            continue
                    
                    logger.info(f"🚀 {symbol}: Ejecutando {action['action']} de {quantity_to_use} @ ${current_price}")
                    
                    result = await self._execute_trade(
                        symbol=symbol,
                        action=action["action"],
                        quantity=quantity_to_use,
                        price=current_price
                    )
                    
                    if result:
                        trading_results.append(result)
                        asset_config.last_action = action["action"]
                        logger.info(f"✅ {symbol}: Trade ejecutado exitosamente")
                        
                        # Registrar métricas de trading usando el nuevo sistema centralizado
                        try:
                            from app.core.metrics_manager import metrics_manager
                            metrics_manager.record_trade_execution(
                                symbol=symbol,
                                side=action["action"],
                                quantity=quantity_to_use,
                                price=current_price,
                                execution_time=0.5  # Tiempo estimado de ejecución
                            )
                        except Exception as e:
                            logger.error(f"Error registrando métricas de trade: {e}")
                    else:
                        logger.error(f"❌ {symbol}: Error ejecutando trade")
                        
                        # Registrar métricas de error usando el nuevo sistema centralizado
                        try:
                            from app.core.metrics_manager import metrics_manager
                            metrics_manager.record_error("trade_execution_failed", "grid_manager")
                        except Exception as e:
                            logger.error(f"Error registrando métricas de error: {e}")
                else:
                    current_price = prices.get(symbol, 0)
                    # Determinar el motivo específico por el que no se ejecuta la orden
                    if not action:
                        reason = "sin señal de trading válida"
                    elif not action.get("action"):
                        reason = "señal de trading inválida"
                    else:
                        reason = "precio no cruzó niveles de grilla o última acción repetida"
                    
                    logger.info(f"⛔ {symbol}: No se ejecuta orden - Motivo: {reason}")
                    logger.info(f"   📊 Precio actual: ${current_price}")
                    logger.info(f"   📈 Niveles de grilla: {asset_config.grid_levels}")
                    logger.info(f"   🔄 Última acción: {asset_config.last_action}")
                    logger.info(f"   📡 Señal recibida: {action}")
                    
                    # Log adicional para debugging de la lógica de grid
                    if asset_config.grid_levels:
                        min_level = min(asset_config.grid_levels)
                        max_level = max(asset_config.grid_levels)
                        logger.info(f"   📋 Rango de grilla: ${min_level} - ${max_level}")
                        if current_price < min_level:
                            logger.info(f"   ⬇️ Precio por debajo del rango mínimo")
                        elif current_price > max_level:
                            logger.info(f"   ⬆️ Precio por encima del rango máximo")
                        else:
                            logger.info(f"   ↔️ Precio dentro del rango, pero no cruzó niveles")
            
            if self.insufficient_funds:
                logger.warning(f"⚠️ Activos con saldo insuficiente: {list(self.insufficient_funds.keys())}")
            
            # Log final del ciclo
            if trading_results:
                logger.info(f"🎉 Ciclo de trading completado exitosamente")
                logger.info(f"📊 Total de operaciones ejecutadas: {len(trading_results)}")
                buy_trades = len([r for r in trading_results if r.action == "BUY"])
                sell_trades = len([r for r in trading_results if r.action == "SELL"])
                logger.info(f"📈 Compras: {buy_trades}, Ventas: {sell_trades}")
            else:
                logger.info(f"ℹ️ Ciclo de trading completado sin operaciones")
                logger.info(f"💡 Posibles razones: precios fuera de rango, sin señales válidas, o saldos insuficientes")
            
            # Actualizar métricas usando el nuevo sistema centralizado y el servicio de rentabilidad
            try:
                from app.core.metrics_manager import metrics_manager
                from app.services.metrics_service import metrics_service
                await metrics_manager.update_all_metrics()
                # Actualiza gauges como profit_total_usdt/portfolio_total_value_usdt con labels esperados
                try:
                    await metrics_service.calculate_portfolio_metrics()
                except Exception:
                    pass
                logger.info("✅ Métricas actualizadas correctamente")
            except Exception as e:
                logger.error(f"Error actualizando métricas: {e}")
            
            # Registrar duración de ciclo grid
            duration = perf_counter() - cycle_start
            try:
                trading_metrics.record_grid_cycle_duration(duration)
            except Exception:
                pass
            return trading_results
            
        except Exception as e:
            logger.error(f"Error ejecutando ciclo de trading: {e}")
            return []

    async def _execute_single_asset_trading(self, symbol: str, quantity: float, current_price: float) -> Optional[TradingResult]:
        """Execute trading for a single asset"""
        try:
            asset_config = self.config.assets.get(symbol)
            if not asset_config:
                return None
            
            action = decide_grid_action(current_price, asset_config.grid_levels, asset_config.last_action)
            
            if not action or not action.get("action"):
                return None
            
            result = await self._execute_trade(
                symbol=symbol,
                action=action["action"],
                quantity=quantity,
                price=current_price
            )
            
            if result:
                asset_config.last_action = action["action"]
            
            return result
            
        except Exception as e:
            logger.error(f"Error ejecutando trading para {symbol}: {e}")
            return None

    async def _place_order(self, symbol: str, action: str, quantity: float) -> Optional[Dict]:
        """Place an order on Binance (Paper Trading or Real) with commission validation"""
        try:
            # Verificar modo Paper Trading
            paper_trading = os.getenv("PAPER_TRADING", "false").lower() == "true"
            
            # Obtener precio actual para cálculos de comisión
            current_price = await self.async_binance.get_price(symbol)
            notional_value = quantity * current_price
            
            # Calcular comisión antes de ejecutar la orden
            commission = commission_manager.calculate_commission(notional_value, 'MARKET', symbol)
            commission_percentage = (commission / notional_value * 100) if notional_value > 0 else 0
            
            logger.info(f"💰 Comisión calculada para {action} {quantity} {symbol}: ${commission:.6f} USDT ({commission_percentage:.3f}%)")
            
            # Validar si la comisión es excesiva (más del 1%)
            if commission_percentage > 1.0:
                logger.warning(f"⚠️ Comisión alta detectada: {commission_percentage:.3f}% para {symbol}")
            
            if paper_trading:
                # Simular orden en modo Paper Trading
                logger.info(f"📄 Simulando orden en modo Paper Trading: {action} {quantity} {symbol}")
                
                # Crear orden simulada con información de comisión
                simulated_order = {
                    'orderId': f"paper_{int(datetime.now().timestamp())}",
                    'symbol': symbol,
                    'side': action,
                    'type': 'MARKET',
                    'quantity': str(quantity),
                    'status': 'FILLED',
                    'price': '0',  # Precio de mercado
                    'executedQty': str(quantity),
                    'cummulativeQuoteQty': '0',
                    'timeInForce': 'GTC',
                    'time': int(datetime.now().timestamp() * 1000),
                    'updateTime': int(datetime.now().timestamp() * 1000),
                    'isWorking': False,
                    'origQuoteOrderQty': '0',
                    'commission_info': {
                        'commission_usdt': commission,
                        'commission_percentage': commission_percentage,
                        'notional_value': notional_value,
                        'order_type': 'MARKET'
                    }
                }
                
                logger.info(f"✅ Orden simulada creada: {simulated_order['orderId']} - Comisión: ${commission:.6f} USDT")
                return simulated_order
            
            else:
                # Orden real en Binance
                if not self.client:
                    logger.error("❌ Cliente de Binance no inicializado para orden real")
                    return None
                
                # Verificar credenciales antes de crear orden real
                if not hasattr(self.client, 'api_key') or not self.client.api_key:
                    logger.error("❌ Cliente de Binance sin credenciales para orden real")
                    return None
                
                # Formatear cantidad evitando notación científica y respetando stepSize
                def _format_quantity(sym: str, qty: float) -> str:
                    limits = self.asset_limits.get(sym)
                    # Precisión por defecto si no hay límites
                    default_step = Decimal('0.00000001')
                    step = default_step
                    if limits and getattr(limits, 'step_size', None):
                        try:
                            step = Decimal(str(limits.step_size))
                        except Exception:
                            step = default_step
                    getcontext().prec = 28
                    q = Decimal(str(qty))
                    # Floor a múltiplos de step
                    units = (q / step).to_integral_value(rounding=ROUND_DOWN)
                    q_adj = units * step
                    precision = max(0, -step.as_tuple().exponent)
                    return f"{q_adj:.{precision}f}"

                qty_str = _format_quantity(symbol, quantity)
                # Asegurar formato fijo (sin notación científica)
                try:
                    limits = self.asset_limits.get(symbol)
                    precision = 8
                    if limits and getattr(limits, 'step_size', None):
                        step = Decimal(str(limits.step_size))
                        precision = max(0, -step.as_tuple().exponent)
                    qty_str = f"{Decimal(qty_str):.{precision}f}"
                except Exception:
                    qty_str = f"{Decimal(str(quantity)):.8f}"
                logger.info(f"💰 Creando orden real en Binance: {action} {qty_str} {symbol}")
                
                # Ejecutar llamada bloqueante en hilo para no bloquear el loop
                def _create_order():
                    # Fallback para BUY con quoteOrderQty (evita problemas de cantidad en BTC)
                    if action.upper() == 'BUY':
                        try:
                            price_now = float(current_price) if current_price else float(asyncio.run(self.async_binance.get_price(symbol)))
                        except Exception:
                            price_now = float(current_price) if current_price else 0.0
                        usdt_amount = max(round(price_now * float(quantity), 2), 10.02)
                        return self.client.create_order(
                            symbol=symbol,
                            side=action,
                            type='MARKET',
                            quoteOrderQty=usdt_amount
                        )
                    return self.client.create_order(
                        symbol=symbol,
                        side=action,
                        type='MARKET',
                        quantity=qty_str
                    )
                order = await asyncio.to_thread(_create_order)
                
                # Agregar información de comisión al resultado
                order['commission_info'] = {
                    'commission_usdt': commission,
                    'commission_percentage': commission_percentage,
                    'notional_value': notional_value,
                    'order_type': 'MARKET'
                }
                
                logger.info(f"✅ Orden real creada: {order.get('orderId', 'unknown')} - Comisión: ${commission:.6f} USDT")
                return order
                
        except Exception as e:
            logger.error(f"❌ Error colocando orden para {symbol}: {e}")
            return None

    def _send_trading_notification(self, result: TradingResult):
        """Send trading notification via Telegram"""
        try:
            message = f"🔄 Trade ejecutado:\n" \
                     f"🪙 {result.symbol}\n" \
                     f"📈 {result.action}\n" \
                     f"📏 {result.quantity}\n" \
                     f"💰 ${result.price:.6f}\n" \
                     f"📊 Estado: {result.status}"
            
            send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Error enviando notificación: {e}")

    async def _save_trade_to_db(self, symbol: str, side: str, quantity: float, price: float, order_id: str):
        """Guarda un trade en la base de datos PostgreSQL con manejo optimizado"""
        db = None
        try:
            from app.db.session import SessionLocal
            from app.models.trade import Trade
            from sqlalchemy import desc
            
            logger.info(f"🔄 Guardando trade en BD: {side} {quantity} {symbol} @ ${price:.6f}")
            
            db = SessionLocal()
            
            if side.upper() == 'SELL':
                # Buscar última BUY sin cerrar para realizar PnL
                open_buy = db.query(Trade).filter(
                    Trade.symbol == symbol,
                    Trade.side == 'BUY',
                    Trade.exit_price == None
                ).order_by(desc(Trade.timestamp)).first()
                if open_buy:
                    open_buy.exit_price = float(price)
                    open_buy.profit_loss = (float(price) - float(open_buy.entry_price)) * float(min(quantity, open_buy.quantity))
                    db.commit()
                    db.refresh(open_buy)
                    logger.info(f"✅ PnL realizado registrado: {open_buy.profit_loss:.6f} USDT en {symbol}")
                else:
                    # Sin BUY abierto: registrar trade SELL como evento de salida sin PnL
                    trade = Trade(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        entry_price=price,
                        timestamp=datetime.now()
                    )
                    db.add(trade)
                    db.commit()
                    db.refresh(trade)
            else:
                # BUY: crear entrada abierta
                trade = Trade(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    entry_price=price,
                    timestamp=datetime.now()
                )
                db.add(trade)
                db.commit()
                db.refresh(trade)
            
            # Validar datos antes de guardar
            if not symbol or not side or quantity <= 0 or price <= 0:
                raise ValueError(f"Datos inválidos: symbol={symbol}, side={side}, quantity={quantity}, price={price}")
            
            logger.info(f"✅ Trade guardado exitosamente en BD - ID: {trade.id}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando trade en BD: {e}")
            logger.error(f"   Detalles: symbol={symbol}, side={side}, quantity={quantity}, price={price}")
            if db:
                try:
                    db.rollback()
                    logger.debug("🔄 Rollback ejecutado en BD debido a error")
                except Exception as rollback_error:
                    logger.error(f"❌ Error en rollback: {rollback_error}")
        finally:
            if db:
                try:
                    db.close()
                except Exception as close_error:
                    logger.error(f"❌ Error cerrando conexión BD: {close_error}")

    async def _execute_trade(self, symbol: str, action: str, quantity: float, price: float):
        """Execute a trade and return the result"""
        try:
            # Place the order
            order = await self._place_order(symbol, action, quantity)
            
            if not order:
                return None
            
            # Create trading result
            result = TradingResult(
                timestamp=datetime.now(),
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=price,
                order_id=order.get('orderId', 'unknown'),
                status=order.get('status', 'unknown'),
                profit=None  # Will be calculated later
            )
            
            # Add to trading history
            self.trading_history.append(result)
            
            # Send notification
            self._send_trading_notification(result)
            
            # Registrar métricas del trade
            try:
                execution_time = 0.1  # Tiempo estimado de ejecución
                success = result.status in ['FILLED', 'PARTIALLY_FILLED']
                # Comentado temporalmente para evitar errores
                # await metrics_service.record_trade_execution(
                #     symbol=symbol,
                #     side=action,
                #     quantity=quantity,
                #     price=price,
                #     success=success,
                #     execution_time=execution_time
                # )
                logger.info(f"📊 Métricas del trade registradas: {action} {quantity} {symbol}")
            except Exception as e:
                logger.error(f"Error registrando métricas del trade: {e}")
            
            # Guardar trade en la base de datos
            try:
                logger.info(f"🔄 Intentando guardar trade en BD: {action} {quantity} {symbol} @ ${price:.6f}")
                await self._save_trade_to_db(symbol, action, quantity, price, order.get('orderId', 'unknown'))
                logger.info(f"✅ Trade guardado exitosamente en BD")
            except Exception as e:
                logger.error(f"❌ Error guardando trade en base de datos: {e}")
                logger.error(f"   Detalles: symbol={symbol}, action={action}, quantity={quantity}, price={price}")
            
            logger.info(f"Trade ejecutado: {action} {quantity} {symbol} a ${price:.6f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error ejecutando trade para {symbol}: {e}")
            return None

    def update_asset_config(self, symbol: str, new_config: Dict) -> bool:
        """Update configuration for a specific asset"""
        try:
            if symbol not in self.config.assets:
                return False
            
            asset_config = self.config.assets[symbol]
            
            # Update fields
            for key, value in new_config.items():
                if hasattr(asset_config, key):
                    setattr(asset_config, key, value)
            
            # Recalculate grid levels
            asset_config.grid_levels = calculate_grid_levels(
                asset_config.min_price,
                asset_config.max_price,
                asset_config.grids
            )
            
            logger.info(f"Updated configuration for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error updating config for {symbol}: {e}")
            return False

    async def reload_configuration(self, config_file_path: str = None) -> bool:
        """Recarga la configuración desde el archivo"""
        try:
            if config_file_path:
                self.config_file_path = config_file_path
            
            if not self.config_file_path:
                logger.error("No se especificó archivo de configuración para recargar")
                return False
            
            logger.info(f"Recargando configuración desde: {self.config_file_path}")
            
            # Crear nuevo grid manager con la configuración actualizada
            new_manager = await create_optimized_grid_manager(self.config_file_path)
            
            if new_manager:
                # Actualizar configuración
                self.config = new_manager.config
                self.asset_limits = new_manager.asset_limits
                
                logger.info("✅ Configuración recargada exitosamente")
                return True
            else:
                logger.error("❌ Error creando nuevo grid manager")
                return False
                
        except Exception as e:
            logger.error(f"Error recargando configuración: {e}")
            return False

    def get_trading_statistics(self) -> Dict:
        """Get comprehensive trading statistics"""
        try:
            if not self.trading_history:
                return {"message": "No trading history available"}
            
            total_trades = len(self.trading_history)
            buy_trades = len([t for t in self.trading_history if t.action == "BUY"])
            sell_trades = len([t for t in self.trading_history if t.action == "SELL"])
            
            # Calculate profits
            total_profit = sum(t.profit or 0 for t in self.trading_history)
            
            # Group by asset
            asset_stats = {}
            for result in self.trading_history:
                if result.symbol not in asset_stats:
                    asset_stats[result.symbol] = {"trades": 0, "profit": 0}
                asset_stats[result.symbol]["trades"] += 1
                asset_stats[result.symbol]["profit"] += result.profit or 0
            
            return {
                "total_trades": total_trades,
                "buy_trades": buy_trades,
                "sell_trades": sell_trades,
                "total_profit": total_profit,
                "asset_statistics": asset_stats,
                "last_trade": self.trading_history[-1].dict() if self.trading_history else None
            }
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {"error": str(e)}
    
    def save_configuration(self, filepath: str) -> bool:
        """Save current configuration to file"""
        try:
            config_data = {
                "assets": {
                    symbol: {
                        "symbol": config.symbol,
                        "min_price": config.min_price,
                        "max_price": config.max_price,
                        "grids": config.grids,
                        "quantity": config.quantity,
                        "is_active": config.is_active,
                        "last_action": config.last_action
                    }
                    for symbol, config in self.config.assets.items()
                },
                "update_interval": self.config.update_interval,
                "min_notional_threshold": self.config.min_notional_threshold,
                "max_concurrent_orders": self.config.max_concurrent_orders
            }
            
            with open(filepath, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Configuration saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def get_insufficient_funds_report(self) -> Dict[str, Dict]:
        """Devuelve un reporte de los activos que no pueden operar por saldo insuficiente y cuánto falta para operar."""
        return self.insufficient_funds


# Factory function for creating grid manager
async def create_optimized_grid_manager(config_file: str) -> Optional[OptimizedGridManager]:
    """
    Factory function to create and initialize an OptimizedGridManager
    """
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        assets = {}
        required_fields = {"symbol", "min_price", "max_price", "grids", "quantity"}
        for key, data in config_data.items():
            # Omitir metadatos y secciones no-asset
            if not isinstance(data, dict):
                continue
            if key.startswith("_") or key in {"system_config"}:
                continue
            # Incluir sólo configuraciones con campos requeridos
            if required_fields.issubset(data.keys()):
                assets[key] = AssetConfig(**data)
            else:
                logger.debug(f"Saltando clave no-asset '{key}' por campos faltantes: {set(data.keys())}")
        
        grid_config = GridManagerConfig(
            assets=assets,
            update_interval=config_data.get("update_interval", 60),
            min_notional_threshold=config_data.get("min_notional_threshold", 10.0)  # Usar 10.0 por defecto
        )
        
        manager = OptimizedGridManager(grid_config)
        manager.config_file_path = config_file  # Guardar ruta del archivo
        await manager._load_asset_limits() # Load limits after creation
        return manager
    except Exception as e:
        logger.error(f"Error creating grid manager: {e}")
        return None 