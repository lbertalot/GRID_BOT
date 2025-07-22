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
    min_notional_threshold: float = Field(default=5.0, ge=1.0)
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
        """Initialize Binance client with proper error handling"""
        try:
            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_API_SECRET")
            
            if not api_key or not api_secret:
                raise ValueError("Binance API credentials not configured")
                
            return Client(api_key, api_secret)
        except Exception as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            raise
    
    async def get_asset_balances(self) -> Dict[str, float]:
        """Get current asset balances asynchronously"""
        try:
            account_info = self.client.get_account()
            balances = {
                b["asset"]: float(b["free"]) 
                for b in account_info["balances"] 
                if float(b["free"]) > 0
            }
            return balances
        except Exception as e:
            logger.error(f"Error fetching balances: {e}")
            return {}
    
    async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for multiple symbols efficiently"""
        try:
            prices = {}
            for symbol in symbols:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                prices[symbol] = float(ticker["price"])
            return prices
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {}
    
    def calculate_optimal_quantities(self, balances: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
        """Calcula las cantidades óptimas para operar, forzando el mínimo de Binance (min_notional)."""
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
            limits = self.asset_limits.get(symbol)
            min_notional = limits.min_notional if limits else 5.0
            min_quantity = min_notional / current_price
            # Forzar la cantidad mínima a la de Binance, ignorando la configurada
            quantity_to_use = min_quantity
            # Ajustar a step_size si corresponde
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
            logger.info("Enviando mensaje de prueba por Telegram al inicio del ciclo de trading...")
            balances = await self.get_asset_balances()
            symbols = [asset.symbol for asset in self.config.assets.values() if asset.is_active]
            prices = await self.get_current_prices(symbols)
            optimal_quantities = self.calculate_optimal_quantities(balances, prices)
            trading_results = []
            for symbol, quantity in optimal_quantities.items():
                asset_config = self.config.assets.get(symbol)
                if not asset_config:
                    continue
                current_price = prices.get(symbol, 0)
                if current_price <= 0:
                    logger.warning(f"Precio para {symbol} es 0 o negativo, saltando operación.")
                    continue
                action = decide_grid_action(prices.get(symbol, 0), asset_config.grid_levels, asset_config.last_action)
                if action and action.get("action"):
                    limits = self.asset_limits.get(symbol)
                    min_notional = limits.min_notional if limits else 5.0
                    min_quantity = min_notional / current_price
                    # Cantidad sugerida por la estrategia (puede ser muy baja)
                    suggested_quantity = quantity
                    # Usar la máxima entre la sugerida y la mínima
                    quantity_to_use = max(suggested_quantity, min_quantity)
                    # Ajustar a step_size
                    if limits and limits.step_size:
                        step_size = limits.step_size
                        precision = int(round(-math.log(step_size, 10), 0))
                        quantity_to_use = float(f"{math.floor(quantity_to_use / step_size) * step_size:.{precision}f}")
                    # Validar saldo
                    base_asset = symbol.replace("USDT", "")
                    available_balance = balances.get(base_asset, 0)
                    if action["action"] == "SELL" and quantity_to_use > available_balance:
                        logger.warning(f"No hay suficiente saldo para vender {quantity_to_use} {base_asset}. Saldo disponible: {available_balance}")
                        continue
                    notional_value = quantity_to_use * current_price
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
                    trading_results.append(result)
                    asset_config.last_action = action["action"]
                else:
                    logger.info(f"No se tomó ninguna acción para {symbol}. Razón: Precio actual ({prices.get(symbol, 0)}) no cruzó ningún nivel de la grilla o la última acción fue la misma.")
            if self.insufficient_funds:
                logger.info("Enviando alerta de activos con saldo insuficiente por Telegram...")
                msg = "⚠️ Activos sin saldo suficiente para operar:\n"
                for symbol, data in self.insufficient_funds.items():
                    msg += (f"{symbol}: saldo actual {data['saldo_actual']:.6f}, "
                            f"necesario {data['cantidad_necesaria']:.6f}, "
                            f"faltante {data['faltante']:.6f}, min_notional {data['min_notional']:.2f}, "
                            f"precio {data['precio_actual']:.6f}\n")
                send_telegram_alert(msg)
            return trading_results
        except Exception as e:
            logger.error(f"Error in grid trading cycle: {e}")
            return []
    
    async def _execute_single_asset_trading(self, symbol: str, quantity: float, current_price: float) -> Optional[TradingResult]:
        """Execute trading for a single asset"""
        try:
            asset_config = self.config.assets.get(symbol)
            if not asset_config:
                return None
            
            # Calculate grid levels
            grid_levels = calculate_grid_levels(
                asset_config.min_price, 
                asset_config.max_price, 
                asset_config.grids
            )
            
            # Decide action
            decision = decide_grid_action(
                current_price, 
                grid_levels, 
                asset_config.last_action or "NONE"
            )
            
            if not decision["action"]:
                return None
            
            # Execute order
            order_result = await self._place_order(symbol, decision["action"], quantity)
            if not order_result:
                return None
            
            # Update last action
            asset_config.last_action = decision["action"]
            
            # Create trading result
            result = TradingResult(
                symbol=symbol,
                action=decision["action"],
                quantity=quantity,
                price=current_price,
                order_id=order_result.get("orderId", ""),
                status=order_result.get("status", ""),
                timestamp=datetime.now()
            )
            
            # Send notification
            await self._send_trading_notification(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing trading for {symbol}: {e}")
            return None
    
    async def _place_order(self, symbol: str, action: str, quantity: float) -> Optional[Dict]:
        """Place order with proper validation and error handling"""
        try:
            result = self.order_validator.place_market_order_with_validation(symbol, action, quantity)
            return result.get("order", {})
        except Exception as e:
            logger.error(f"Error placing order for {symbol}: {e}")
            return None
    
    async def _send_trading_notification(self, result: TradingResult):
        """Send trading notification to Telegram"""
        try:
            message = (
                f"🤖 GridBot ejecutó {result.action} {result.quantity} {result.symbol} "
                f"a ${result.price:.6f}\n"
                f"📋 Orden ID: {result.order_id}\n"
                f"📊 Status: {result.status}"
            )
            send_telegram_alert(message)
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    async def _execute_trade(self, symbol: str, action: str, quantity: float, price: float):
        """
        Ejecuta una orden en Binance y la registra en la base de datos.
        Retorna un TradingResult para el logger.
        """
        try:
            # Ejecutar orden en Binance
            if action == "BUY":
                order = self.client.order_market_buy(symbol=symbol, quantity=quantity)
            elif action == "SELL":
                order = self.client.order_market_sell(symbol=symbol, quantity=quantity)
            else:
                raise ValueError(f"Acción no soportada: {action}")

            entry_price = float(order['fills'][0]['price']) if 'fills' in order and order['fills'] else price
            status = order.get('status', 'UNKNOWN')
            ts = datetime.utcnow()

            # Registrar en la base de datos
            db_user = os.getenv("POSTGRES_USER")
            db_pass = os.getenv("POSTGRES_PASSWORD")
            db_name = os.getenv("POSTGRES_DB")
            db_host = os.getenv("POSTGRES_HOST", "db")
            conn = await asyncpg.connect(user=db_user, password=db_pass, database=db_name, host=db_host)
            await conn.execute('''
                INSERT INTO trades (symbol, side, quantity, entry_price, timestamp)
                VALUES ($1, $2, $3, $4, $5)
            ''', symbol, action, quantity, entry_price, ts)
            await conn.close()

            # Alerta Telegram
            send_telegram_alert(f"✅ Orden ejecutada: {action} {quantity} {symbol} @ ${entry_price:.4f} (status: {status})")
            return TradingResult(
                timestamp=ts,
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=entry_price,
                order_id=order.get('orderId', None),
                status=status,
                profit=None
            )
        except Exception as e:
            send_telegram_alert(f"❌ Error ejecutando orden {action} {quantity} {symbol}: {e}")
            logger.error(f"Error ejecutando orden {action} {quantity} {symbol}: {e}")
            return None

    def update_asset_config(self, symbol: str, new_config: Dict) -> bool:
        """Update configuration for a specific asset"""
        try:
            if symbol not in self.config.assets:
                return False
            
            current_config = self.config.assets[symbol]
            for key, value in new_config.items():
                if hasattr(current_config, key):
                    setattr(current_config, key, value)
            
            logger.info(f"Updated configuration for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error updating config for {symbol}: {e}")
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
            min_notional_threshold=config_data.get("min_notional_threshold", 10.0)
        )
        
        manager = OptimizedGridManager(grid_config)
        await manager._load_asset_limits() # Load limits after creation
        return manager
    except Exception as e:
        logger.error(f"Error creating grid manager: {e}")
        return None 