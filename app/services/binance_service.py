import os
import time
import logging
from typing import Dict, Any, Optional, List
from binance import Client
from binance.exceptions import BinanceAPIException
from app.core.metrics import record_binance_api_call, binance_connection_status

logger = logging.getLogger(__name__)

class BinanceService:
    """Servicio para interactuar con la API de Binance"""
    
    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.client = None
        self.simulation_mode = False
        self._initialize_client()
    
    def _initialize_client(self):
        """Inicializa el cliente de Binance con manejo de errores"""
        try:
            if not self.api_key or not self.api_secret:
                logger.warning("Credenciales de Binance no configuradas. Activando modo simulación.")
                self.simulation_mode = True
                binance_connection_status.set(0)
                return
            
            # Intentar crear el cliente
            self.client = Client(self.api_key, self.api_secret)
            
            # Verificar credenciales con una llamada simple
            start_time = time.time()
            account_info = self.client.get_account()
            duration = time.time() - start_time
            
            record_binance_api_call("get_account", "success", duration)
            binance_connection_status.set(1)
            
            logger.info("✅ Cliente de Binance inicializado correctamente")
            logger.info(f"   Tipo de cuenta: {account_info.get('accountType', 'N/A')}")
            
        except BinanceAPIException as e:
            if e.code == -1022:
                logger.error(f"❌ Error de autenticación Binance (1022): {e.message}")
                logger.warning("🔧 Activando modo simulación debido a credenciales inválidas")
                self.simulation_mode = True
                binance_connection_status.set(0)
            else:
                logger.error(f"❌ Error de Binance API: {e}")
                self.simulation_mode = True
                binance_connection_status.set(0)
                
        except Exception as e:
            logger.error(f"❌ Error inesperado inicializando Binance: {e}")
            self.simulation_mode = True
            binance_connection_status.set(0)
    
    def get_account_info(self) -> Dict[str, Any]:
        """Obtiene información de la cuenta"""
        if self.simulation_mode:
            logger.info("🔄 Modo simulación: Retornando datos simulados de cuenta")
            return self._get_simulated_account_info()
        
        try:
            start_time = time.time()
            account_info = self.client.get_account()
            duration = time.time() - start_time
            
            record_binance_api_call("get_account", "success", duration)
            return account_info
            
        except BinanceAPIException as e:
            record_binance_api_call("get_account", f"error_{e.code}", 0)
            logger.error(f"Error obteniendo información de cuenta: {e}")
            raise
    
    def get_balance(self, asset: str) -> Dict[str, Any]:
        """Obtiene el balance de un activo específico"""
        if self.simulation_mode:
            logger.info(f"🔄 Modo simulación: Retornando balance simulado para {asset}")
            return self._get_simulated_balance(asset)
        
        try:
            start_time = time.time()
            balance = self.client.get_asset_balance(asset=asset)
            duration = time.time() - start_time
            
            record_binance_api_call("get_asset_balance", "success", duration)
            return balance
            
        except BinanceAPIException as e:
            record_binance_api_call("get_asset_balance", f"error_{e.code}", 0)
            logger.error(f"Error obteniendo balance de {asset}: {e}")
            raise
    
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Obtiene información de un símbolo"""
        if self.simulation_mode:
            logger.info(f"🔄 Modo simulación: Retornando información simulada para {symbol}")
            return self._get_simulated_symbol_info(symbol)
        
        try:
            start_time = time.time()
            exchange_info = self.client.get_exchange_info()
            duration = time.time() - start_time
            
            record_binance_api_call("get_exchange_info", "success", duration)
            
            # Buscar el símbolo específico
            for symbol_info in exchange_info['symbols']:
                if symbol_info['symbol'] == symbol:
                    return symbol_info
            
            raise ValueError(f"Símbolo {symbol} no encontrado")
            
        except BinanceAPIException as e:
            record_binance_api_call("get_exchange_info", f"error_{e.code}", 0)
            logger.error(f"Error obteniendo información de símbolo {symbol}: {e}")
            raise
    
    def get_current_price(self, symbol: str) -> float:
        """Obtiene el precio actual de un símbolo"""
        if self.simulation_mode:
            logger.info(f"🔄 Modo simulación: Retornando precio simulado para {symbol}")
            return self._get_simulated_price(symbol)
        
        try:
            start_time = time.time()
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            duration = time.time() - start_time
            
            record_binance_api_call("get_symbol_ticker", "success", duration)
            return float(ticker['price'])
            
        except BinanceAPIException as e:
            record_binance_api_call("get_symbol_ticker", f"error_{e.code}", 0)
            logger.error(f"Error obteniendo precio de {symbol}: {e}")
            raise
    
    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        """Coloca una orden en Binance"""
        if self.simulation_mode:
            logger.info(f"🔄 Modo simulación: Simulando orden {side} {quantity} {symbol} @ {price}")
            return self._simulate_order(symbol, side, order_type, quantity, price)
        
        try:
            start_time = time.time()
            
            if order_type == "MARKET":
                if side == "BUY":
                    order = self.client.order_market_buy(symbol=symbol, quantity=quantity)
                else:
                    order = self.client.order_market_sell(symbol=symbol, quantity=quantity)
            else:  # LIMIT
                if side == "BUY":
                    order = self.client.order_limit_buy(symbol=symbol, quantity=quantity, price=str(price))
                else:
                    order = self.client.order_limit_sell(symbol=symbol, quantity=quantity, price=str(price))
            
            duration = time.time() - start_time
            record_binance_api_call("place_order", "success", duration)
            
            logger.info(f"✅ Orden colocada exitosamente: {order['orderId']}")
            return order
            
        except BinanceAPIException as e:
            record_binance_api_call("place_order", f"error_{e.code}", 0)
            logger.error(f"Error colocando orden: {e}")
            raise
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene órdenes abiertas"""
        if self.simulation_mode:
            logger.info("🔄 Modo simulación: Retornando órdenes simuladas")
            return self._get_simulated_open_orders(symbol)
        
        try:
            start_time = time.time()
            orders = self.client.get_open_orders(symbol=symbol)
            duration = time.time() - start_time
            
            record_binance_api_call("get_open_orders", "success", duration)
            return orders
            
        except BinanceAPIException as e:
            record_binance_api_call("get_open_orders", f"error_{e.code}", 0)
            logger.error(f"Error obteniendo órdenes abiertas: {e}")
            raise
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancela una orden"""
        if self.simulation_mode:
            logger.info(f"🔄 Modo simulación: Simulando cancelación de orden {order_id}")
            return self._simulate_cancel_order(symbol, order_id)
        
        try:
            start_time = time.time()
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            duration = time.time() - start_time
            
            record_binance_api_call("cancel_order", "success", duration)
            return result
            
        except BinanceAPIException as e:
            record_binance_api_call("cancel_order", f"error_{e.code}", 0)
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
                {"asset": "ETH", "free": "0.1", "locked": "0.0"}
            ]
        }
    
    def _get_simulated_balance(self, asset: str) -> Dict[str, Any]:
        """Retorna balance simulado"""
        balances = {
            "USDT": {"free": "1000.0", "locked": "0.0"},
            "BTC": {"free": "0.01", "locked": "0.0"},
            "ETH": {"free": "0.1", "locked": "0.0"}
        }
        
        return {
            "asset": asset,
            "free": balances.get(asset, "0.0")["free"],
            "locked": balances.get(asset, "0.0")["locked"]
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
                    "stepSize": "0.00001"
                },
                {
                    "filterType": "MIN_NOTIONAL",
                    "minNotional": "10.00000000"
                }
            ]
        }
    
    def _get_simulated_price(self, symbol: str) -> float:
        """Retorna precio simulado"""
        prices = {
            "BTCUSDT": 50000.0,
            "ETHUSDT": 3000.0,
            "ADAUSDT": 0.5,
            "DOTUSDT": 7.0
        }
        return prices.get(symbol, 100.0)
    
    def _simulate_order(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
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
            "isWorking": False
        }
    
    def _get_simulated_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
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
            "side": "BUY"
        }
