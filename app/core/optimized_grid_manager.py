"""
Optimized Grid Manager for Multi-Asset Trading
Following FastAPI best practices and .cursorrules
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
import os
import asyncpg
import math

import requests
from pydantic import BaseModel, Field, validator
from binance import Client

from app.services.telegram_alert import send_telegram_alert
from app.services.grid_strategy import decide_grid_action, calculate_grid_levels
from app.services.order_validation import OrderValidator
from app.models.asset_limit import AssetLimit
from app.services.risk_manager import risk_manager, RiskStatus
from app.services.metrics_service import metrics_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AssetConfig(BaseModel):
    """Configuration for a single trading asset"""
    symbol: str
    min_price: float
    max_price: float
    grids: int
    quantity: float
    is_active: bool = True
    last_action: Optional[str] = None
    grid_levels: List[float] = Field(default_factory=list)

    @validator('grid_levels', always=True)
    def calculate_grid_levels_on_init(cls, v, values):
        if not v:  # Only calculate if not already set
            return calculate_grid_levels(
                values.get('min_price'),
                values.get('max_price'),
                values.get('grids')
            )
        return v


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
        
    async def _load_asset_limits(self):
        """Load asset trading limits from the database."""
        db_user = os.getenv("POSTGRES_USER")
        db_pass = os.getenv("POSTGRES_PASSWORD")
        db_name = os.getenv("POSTGRES_DB")
        db_host = os.getenv("POSTGRES_HOST", "db")
        conn = None
        try:
            conn = await asyncpg.connect(user=db_user, password=db_pass, database=db_name, host=db_host)
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
        """Initialize Binance client with API credentials"""
        try:
            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_SECRET_KEY")  # Corregido para usar BINANCE_SECRET_KEY
            
            if not api_key or not api_secret:
                logger.error("Faltan credenciales de Binance en las variables de entorno.")
                logger.error(f"API_KEY presente: {bool(api_key)}")
                logger.error(f"SECRET_KEY presente: {bool(api_secret)}")
                return None
            
            logger.info("✅ Credenciales de Binance encontradas, inicializando cliente...")
            logger.info(f"API_KEY: {api_key[:10]}...")
            logger.info(f"SECRET_KEY: {api_secret[:10]}...")
            
            client = Client(api_key, api_secret)
            
            # Probar la conexión inmediatamente
            try:
                test_account = client.get_account()
                logger.info(f"✅ Cliente de Binance inicializado correctamente - Tipo de cuenta: {test_account.get('accountType', 'N/A')}")
            except Exception as test_error:
                logger.error(f"❌ Error probando cliente de Binance: {test_error}")
                return None
            
            return client
        except Exception as e:
            logger.error(f"Error inicializando cliente Binance: {e}")
            return None

    async def get_asset_balances(self) -> Dict[str, float]:
        """Get current asset balances from Binance"""
        try:
            if not self.client:
                logger.error("❌ Cliente de Binance no inicializado")
                return {}
            
            logger.info("🔄 Obteniendo información de cuenta de Binance...")
            account_info = self.client.get_account()
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
            
            prices = {}
            for symbol in symbols:
                try:
                    ticker = self.client.get_symbol_ticker(symbol=symbol)
                    prices[symbol] = float(ticker['price'])
                except Exception as e:
                    logger.warning(f"Error obteniendo precio para {symbol}: {e}")
                    prices[symbol] = 0
            
            return prices
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
            
            # Verificar que cumple con min_notional del sistema
            min_notional = self.config.min_notional_threshold
            notional_value = quantity_to_use * current_price
            
            if notional_value < min_notional:
                logger.warning(f"La cantidad configurada para {symbol} no cumple min_notional. "
                             f"Valor: {notional_value:.4f}, Mínimo: {min_notional}")
                # Calcular cantidad mínima requerida
                min_quantity = min_notional / current_price
                quantity_to_use = min_quantity
            
            # Ajustar a step_size si corresponde
            limits = self.asset_limits.get(symbol)
            if limits and limits.step_size:
                step_size = limits.step_size
                precision = int(round(-math.log(step_size, 10), 0))
                quantity_to_use = float(f"{math.floor(quantity_to_use / step_size) * step_size:.{precision}f}")
            
            if current_balance >= quantity_to_use:
                optimal_quantities[symbol] = quantity_to_use
            else:
                missing = max(0, quantity_to_use - current_balance)
                self.insufficient_funds[symbol] = {
                    "saldo_actual": current_balance,
                    "cantidad_necesaria": quantity_to_use,
                    "faltante": missing,
                    "min_notional": min_notional,
                    "precio_actual": current_price
                }
        
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
            # Verificar límites de riesgo antes de ejecutar trading
            risk_status = await risk_manager.check_portfolio_risk()
            
            if risk_status == RiskStatus.STOP_TRADING:
                logger.warning("Trading detenido por límites de riesgo críticos")
                send_telegram_alert("🚨 Trading detenido por límites de riesgo críticos")
                return []
            
            if risk_status == RiskStatus.DANGER:
                logger.warning("Trading en modo de riesgo alto - ejecutando con precaución")
                send_telegram_alert("⚠️ Trading en modo de riesgo alto - ejecutando con precaución")
            
            # Verificar si el trading está habilitado
            if not risk_manager.trading_enabled:
                logger.info("Trading deshabilitado por gestión de riesgos")
                return []
            
            logger.info("Iniciando ciclo de trading con verificación de riesgos...")
            balances = await self.get_asset_balances()
            symbols = [asset.symbol for asset in self.config.assets.values() if asset.is_active]
            prices = await self.get_current_prices(symbols)
            optimal_quantities = self.calculate_optimal_quantities(balances, prices)
            trading_results = []
            
            for symbol, quantity in optimal_quantities.items():
                asset_config = self.config.assets.get(symbol)
                if not asset_config:
                    continue
                
                # Verificar riesgo específico del activo
                asset_risk_status = await risk_manager.check_asset_risk(symbol)
                if asset_risk_status == RiskStatus.STOP_TRADING:
                    logger.warning(f"Trading detenido para {symbol} por riesgo crítico")
                    continue
                
                if asset_risk_status == RiskStatus.DANGER:
                    # Ejecutar stop-loss si es necesario
                    await risk_manager.execute_stop_loss(symbol)
                    logger.warning(f"Stop-loss ejecutado para {symbol}")
                    continue
                    
                current_price = prices.get(symbol, 0)
                if current_price <= 0:
                    logger.warning(f"Precio para {symbol} es 0 o negativo, saltando operación.")
                    continue
                
                action = decide_grid_action(prices.get(symbol, 0), asset_config.grid_levels, asset_config.last_action)
                
                if action and action.get("action"):
                    # Usar la cantidad calculada (que ya incluye validaciones)
                    quantity_to_use = quantity
                    
                    # Validar saldo
                    base_asset = symbol.replace("USDT", "")
                    available_balance = balances.get(base_asset, 0)
                    
                    if action["action"] == "SELL" and quantity_to_use > available_balance:
                        logger.warning(f"No hay suficiente saldo para vender {quantity_to_use} {base_asset}. Saldo disponible: {available_balance}")
                        continue
                    
                    # Verificar min_notional
                    notional_value = quantity_to_use * current_price
                    min_notional = self.config.min_notional_threshold
                    
                    if notional_value < min_notional:
                        logger.warning(f"La orden para {symbol} no cumple el valor nocional mínimo. "
                                     f"Valor: {notional_value:.4f}, Mínimo: {min_notional}")
                        continue
                    
                    result = await self._execute_trade(
                        symbol=symbol,
                        action=action["action"],
                        quantity=quantity_to_use,
                        price=current_price
                    )
                    
                    if result:
                        trading_results.append(result)
                        asset_config.last_action = action["action"]
                else:
                    logger.info(f"No se tomó ninguna acción para {symbol}. Razón: Precio actual ({prices.get(symbol, 0)}) no cruzó ningún nivel de la grilla o la última acción fue la misma.")
            
            if self.insufficient_funds:
                logger.warning(f"Activos con saldo insuficiente: {list(self.insufficient_funds.keys())}")
            
            # Actualizar métricas de rentabilidad
            try:
                await metrics_service.calculate_portfolio_metrics()
                await metrics_service.update_balance_metrics(balances)
                logger.info("✅ Métricas de rentabilidad actualizadas")
            except Exception as e:
                logger.error(f"Error actualizando métricas: {e}")
            
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
        """Place an order on Binance"""
        try:
            if not self.client:
                return None
            
            order = self.client.create_order(
                symbol=symbol,
                side=action,
                type='MARKET',
                quantity=quantity
            )
            
            return order
        except Exception as e:
            logger.error(f"Error colocando orden para {symbol}: {e}")
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
        """Guarda un trade en la base de datos PostgreSQL"""
        try:
            from app.db.session import SessionLocal
            from app.models.trade import Trade
            
            db = SessionLocal()
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
            logger.info(f"✅ Trade guardado en BD: {side} {quantity} {symbol} @ ${price:.6f}")
            db.close()
        except Exception as e:
            logger.error(f"Error guardando trade en BD: {e}")
            if 'db' in locals():
                db.close()

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
                await metrics_service.record_trade_execution(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    price=price,
                    success=success,
                    execution_time=execution_time
                )
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
        for symbol, data in config_data.items():
            if symbol != "_optimization_metadata":
                assets[symbol] = AssetConfig(**data)
        
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