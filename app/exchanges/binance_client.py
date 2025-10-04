"""
Cliente Binance mejorado con validación de filtros, rate limiting y WebSocket.
Implementa todas las funcionalidades de la TAREA A.
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import aiohttp
from aiohttp import ClientTimeout
import tenacity
import websockets
from dataclasses import dataclass
from datetime import datetime, timedelta
import random

from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge

from .exceptions import SymbolFilterError, RateLimitError, WebSocketError, ConnectionError

# Métricas Prometheus
ORDERS_REJECTED_TOTAL = Counter(
    'orders_rejected_total', 
    'Total orders rejected by validation',
    ['reason', 'symbol']
)

API_RATE_LIMIT_HITS_TOTAL = Counter(
    'api_rate_limit_hits_total',
    'Total API rate limit hits',
    ['endpoint']
)

API_RETRIES_TOTAL = Counter(
    'api_retries_total',
    'Total API retries',
    ['endpoint', 'reason']
)

WS_LAG_MS = Histogram(
    'ws_lag_ms',
    'WebSocket lag in milliseconds',
    ['symbol', 'type']
)

WS_CONNECTED = Gauge(
    'ws_connected',
    'WebSocket connection status',
    ['symbol', 'type']
)

# Configuración
WS_LAG_THRESHOLD = 3000  # 3 segundos
WS_FAIL_SEC = 30  # 30 segundos de desconexión antes de fallback
EXCHANGE_INFO_CACHE_TTL = 300  # 5 minutos


@dataclass
class SymbolFilter:
    """Filtros de símbolo de Binance."""
    symbol: str
    price_filter: Optional[Dict[str, Any]] = None
    lot_size_filter: Optional[Dict[str, Any]] = None
    min_notional_filter: Optional[Dict[str, Any]] = None
    iceberg_parts_filter: Optional[Dict[str, Any]] = None
    market_lot_size_filter: Optional[Dict[str, Any]] = None
    max_num_orders_filter: Optional[Dict[str, Any]] = None
    max_num_algo_orders_filter: Optional[Dict[str, Any]] = None
    max_num_icberg_parts_filter: Optional[Dict[str, Any]] = None
    max_position_filter: Optional[Dict[str, Any]] = None
    percent_price_filter: Optional[Dict[str, Any]] = None
    percent_price_by_side_filter: Optional[Dict[str, Any]] = None
    notional_filter: Optional[Dict[str, Any]] = None
    max_num_orders_filter: Optional[Dict[str, Any]] = None


class TokenBucketRateLimiter:
    """Rate limiter basado en token bucket con jitter y backoff."""
    
    def __init__(self, capacity: int, refill_rate: float, endpoint: str):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.endpoint = endpoint
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """Adquiere un token del bucket."""
        async with self._lock:
            now = time.time()
            time_passed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + time_passed * self.refill_rate)
            self.last_refill = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            
            # Rate limit hit
            API_RATE_LIMIT_HITS_TOTAL.labels(endpoint=self.endpoint).inc()
            return False
    
    async def wait_for_token(self, max_wait: float = 60.0) -> None:
        """Espera hasta que haya un token disponible."""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if await self.acquire():
                return
            
            # Backoff exponencial con jitter
            wait_time = min(2 ** (time.time() - start_time), 10.0)
            jitter = random.uniform(0.1, 0.3) * wait_time
            await asyncio.sleep(wait_time + jitter)
        
        raise RateLimitError(self.endpoint)


class BinanceClient:
    """
    Cliente Binance mejorado con validación de filtros, rate limiting y WebSocket.
    """
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://testnet.binance.vision" if testnet else "https://api.binance.com"
        self.ws_url = "wss://testnet.binance.vision/ws" if testnet else "wss://stream.binance.com:9443/ws"
        
        # Rate limiters por endpoint
        self.rate_limiters = {
            "order": TokenBucketRateLimiter(10, 1.0, "order"),  # 10 órdenes por segundo
            "exchange_info": TokenBucketRateLimiter(20, 2.0, "exchange_info"),
            "account": TokenBucketRateLimiter(5, 0.5, "account"),
            "market_data": TokenBucketRateLimiter(50, 5.0, "market_data")
        }
        
        # Cache de exchange info
        self._exchange_info_cache: Dict[str, SymbolFilter] = {}
        self._cache_timestamp = 0
        
        # WebSocket connections
        self._ws_connections: Dict[str, Any] = {}
        self._ws_last_ping: Dict[str, float] = {}
        
        self.logger = logging.getLogger(__name__)
    
    async def get_exchange_info(self, force_refresh: bool = False) -> Dict[str, SymbolFilter]:
        """
        Obtiene información del exchange con cache TTL configurable.
        
        Args:
            force_refresh: Si True, ignora el cache y obtiene datos frescos
            
        Returns:
            Dict con filtros de símbolos
        """
        now = time.time()
        
        # Verificar cache
        if not force_refresh and (now - self._cache_timestamp) < EXCHANGE_INFO_CACHE_TTL:
            return self._exchange_info_cache
        
        # Rate limiting
        await self.rate_limiters["exchange_info"].wait_for_token()
        
        try:
            timeout = ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/api/v3/exchangeInfo") as response:
                    if response.status != 200:
                        raise ConnectionError(f"Failed to get exchange info: {response.status}", 
                                            f"{self.base_url}/api/v3/exchangeInfo")
                    
                    data = await response.json()
                    
                    # Procesar filtros
                    for symbol_data in data.get("symbols", []):
                        symbol = symbol_data["symbol"]
                        filters = {}
                        
                        for filter_data in symbol_data.get("filters", []):
                            filter_type = filter_data["filterType"]
                            filters[f"{filter_type.lower()}_filter"] = filter_data
                        
                        self._exchange_info_cache[symbol] = SymbolFilter(symbol=symbol, **filters)
                    
                    self._cache_timestamp = now
                    return self._exchange_info_cache
                    
        except Exception as e:
            self.logger.error(f"Error getting exchange info: {e}")
            raise

    @tenacity.retry(wait=tenacity.wait_exponential(max=10), stop=tenacity.stop_after_attempt(5), reraise=True)
    async def _get(self, session: aiohttp.ClientSession, url: str) -> Any:
        async with session.get(url) as response:
            if response.status != 200:
                raise ConnectionError(f"GET {url} -> {response.status}", url)
            return await response.json()
    
    def normalize_price(self, symbol: str, price: float) -> float:
        """
        Normaliza el precio según los filtros del símbolo.
        
        Args:
            symbol: Símbolo del trading pair
            price: Precio a normalizar
            
        Returns:
            Precio normalizado
        """
        if symbol not in self._exchange_info_cache:
            raise SymbolFilterError(symbol, "Symbol not found in cache", "SYMBOL_NOT_FOUND", price, None)
        
        symbol_filter = self._exchange_info_cache[symbol]
        
        if symbol_filter.price_filter:
            tick_size = float(symbol_filter.price_filter["tickSize"])
            normalized_price = round(price / tick_size) * tick_size
            return normalized_price
        
        return price
    
    def normalize_qty(self, symbol: str, qty: float) -> float:
        """
        Normaliza la cantidad según los filtros del símbolo.
        
        Args:
            symbol: Símbolo del trading pair
            qty: Cantidad a normalizar
            
        Returns:
            Cantidad normalizada
        """
        if symbol not in self._exchange_info_cache:
            raise SymbolFilterError(symbol, "Symbol not found in cache", "SYMBOL_NOT_FOUND", qty, None)
        
        symbol_filter = self._exchange_info_cache[symbol]
        
        if symbol_filter.lot_size_filter:
            step_size = float(symbol_filter.lot_size_filter["stepSize"])
            precision = len(str(step_size).split('.')[-1].rstrip('0'))
            normalized_qty = round(qty, precision)
            return normalized_qty
        
        return qty
    
    def validate_order_params(self, symbol: str, price: float, qty: float, side: str = "BUY") -> None:
        """
        Valida los parámetros de orden contra los filtros del símbolo.
        
        Args:
            symbol: Símbolo del trading pair
            price: Precio de la orden
            qty: Cantidad de la orden
            side: Lado de la orden (BUY/SELL)
            
        Raises:
            SymbolFilterError: Si la validación falla
        """
        if symbol not in self._exchange_info_cache:
            raise SymbolFilterError(symbol, "Symbol not found in cache", "SYMBOL_NOT_FOUND", 
                                  {"price": price, "qty": qty}, None)
        
        symbol_filter = self._exchange_info_cache[symbol]
        
        # Validar precio mínimo
        if symbol_filter.price_filter:
            min_price = float(symbol_filter.price_filter["minPrice"])
            max_price = float(symbol_filter.price_filter["maxPrice"])
            tick_size = float(symbol_filter.price_filter["tickSize"])
            
            if price < min_price:
                ORDERS_REJECTED_TOTAL.labels(reason="price_below_min", symbol=symbol).inc()
                raise SymbolFilterError(symbol, "Price below minimum", "PRICE_FILTER", 
                                      price, min_price)
            
            if price > max_price:
                ORDERS_REJECTED_TOTAL.labels(reason="price_above_max", symbol=symbol).inc()
                raise SymbolFilterError(symbol, "Price above maximum", "PRICE_FILTER", 
                                      price, max_price)
            
            # Validar tick size
            if price % tick_size != 0:
                ORDERS_REJECTED_TOTAL.labels(reason="invalid_tick_size", symbol=symbol).inc()
                raise SymbolFilterError(symbol, "Price not aligned with tick size", "PRICE_FILTER", 
                                      price, tick_size)
        
        # Validar cantidad
        if symbol_filter.lot_size_filter:
            min_qty = float(symbol_filter.lot_size_filter["minQty"])
            max_qty = float(symbol_filter.lot_size_filter["maxQty"])
            step_size = float(symbol_filter.lot_size_filter["stepSize"])
            
            if qty < min_qty:
                ORDERS_REJECTED_TOTAL.labels(reason="qty_below_min", symbol=symbol).inc()
                raise SymbolFilterError(symbol, "Quantity below minimum", "LOT_SIZE_FILTER", 
                                      qty, min_qty)
            
            if qty > max_qty:
                ORDERS_REJECTED_TOTAL.labels(reason="qty_above_max", symbol=symbol).inc()
                raise SymbolFilterError(symbol, "Quantity above maximum", "LOT_SIZE_FILTER", 
                                      qty, max_qty)
            
            # Validar step size
            if qty % step_size != 0:
                ORDERS_REJECTED_TOTAL.labels(reason="invalid_step_size", symbol=symbol).inc()
                raise SymbolFilterError(symbol, "Quantity not aligned with step size", "LOT_SIZE_FILTER", 
                                      qty, step_size)
        
        # Validar notional mínimo
        if symbol_filter.min_notional_filter:
            min_notional = float(symbol_filter.min_notional_filter["minNotional"])
            notional = price * qty
            
            if notional < min_notional:
                ORDERS_REJECTED_TOTAL.labels(reason="notional_below_min", symbol=symbol).inc()
                raise SymbolFilterError(symbol, "Notional below minimum", "MIN_NOTIONAL_FILTER", 
                                      notional, min_notional)
    
    async def create_order(self, symbol: str, side: str, order_type: str, 
                          quantity: float, price: Optional[float] = None, 
                          time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Crea una orden con validación completa y rate limiting.
        
        Args:
            symbol: Símbolo del trading pair
            side: Lado de la orden (BUY/SELL)
            order_type: Tipo de orden (LIMIT/MARKET)
            quantity: Cantidad
            price: Precio (requerido para órdenes LIMIT)
            time_in_force: Tiempo en vigor
            
        Returns:
            Respuesta de la API de Binance
        """
        # Rate limiting
        await self.rate_limiters["order"].wait_for_token()
        
        # Validar parámetros
        if price:
            normalized_price = self.normalize_price(symbol, price)
            self.validate_order_params(symbol, normalized_price, quantity, side)
        else:
            # Para órdenes de mercado, solo validar cantidad
            normalized_qty = self.normalize_qty(symbol, quantity)
            # Validación básica de cantidad
            if symbol in self._exchange_info_cache:
                symbol_filter = self._exchange_info_cache[symbol]
                if symbol_filter.lot_size_filter:
                    min_qty = float(symbol_filter.lot_size_filter["minQty"])
                    if normalized_qty < min_qty:
                        raise SymbolFilterError(symbol, "Quantity below minimum", "LOT_SIZE_FILTER", 
                                              normalized_qty, min_qty)
        
        # Construir payload
        payload = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": self.normalize_qty(symbol, quantity),
            "timestamp": int(time.time() * 1000)
        }
        
        if price:
            payload["price"] = normalized_price
            payload["timeInForce"] = time_in_force
        
        # Nota: este cliente no firma HMAC en este módulo. Debe usarse sólo para simulación/validación.
        # Si se requiere integración real, implementar firma HMAC aquí o usar el cliente oficial.
        return {
            "symbol": symbol,
            "orderId": int(time.time() * 1000),
            "status": "NEW",
            "price": normalized_price if price else "0",
            "quantity": payload["quantity"],
            "side": side,
            "type": order_type
        }
    
    async def start_websocket(self, symbol: str, stream_type: str = "bookTicker") -> None:
        """
        Inicia conexión WebSocket para un símbolo.
        
        Args:
            symbol: Símbolo del trading pair
            stream_type: Tipo de stream (bookTicker, trade, userData)
        """
        stream_name = f"{symbol.lower()}@{stream_type}"
        ws_url = f"{self.ws_url}/{stream_name}"
        
        try:
            websocket = await websockets.connect(ws_url)
            self._ws_connections[stream_name] = websocket
            self._ws_last_ping[stream_name] = time.time()
            WS_CONNECTED.labels(symbol=symbol, type=stream_type).set(1)
            
            self.logger.info(f"WebSocket connected for {stream_name}")
            
            # Iniciar loop de recepción
            asyncio.create_task(self._websocket_receiver(stream_name, symbol, stream_type))
            
        except Exception as e:
            self.logger.error(f"Failed to connect WebSocket for {stream_name}: {e}")
            WS_CONNECTED.labels(symbol=symbol, type=stream_type).set(0)
            raise WebSocketError(f"Failed to connect: {e}", symbol, stream_type)
    
    async def _websocket_receiver(self, stream_name: str, symbol: str, stream_type: str) -> None:
        """Loop de recepción de mensajes WebSocket."""
        websocket = self._ws_connections.get(stream_name)
        if not websocket:
            return
        
        try:
            async for message in websocket:
                # Calcular lag
                receive_time = time.time()
                data = json.loads(message)
                
                if "E" in data:  # Timestamp del exchange
                    exchange_time = data["E"] / 1000.0
                    lag_ms = (receive_time - exchange_time) * 1000
                    WS_LAG_MS.labels(symbol=symbol, type=stream_type).observe(lag_ms)
                    
                    # Verificar si el lag es muy alto
                    if lag_ms > WS_LAG_THRESHOLD:
                        self.logger.warning(f"High WebSocket lag for {stream_name}: {lag_ms:.2f}ms")
                
                # Actualizar último ping
                self._ws_last_ping[stream_name] = receive_time
                
                # Procesar mensaje según el tipo
                await self._process_websocket_message(stream_name, data)
                
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning(f"WebSocket connection closed for {stream_name}")
            WS_CONNECTED.labels(symbol=symbol, type=stream_type).set(0)
            
            # Intentar reconectar después de un delay
            await asyncio.sleep(5)
            await self.start_websocket(symbol, stream_type)
            
        except Exception as e:
            self.logger.error(f"Error in WebSocket receiver for {stream_name}: {e}")
            WS_CONNECTED.labels(symbol=symbol, type=stream_type).set(0)
    
    async def _process_websocket_message(self, stream_name: str, data: Dict[str, Any]) -> None:
        """Procesa mensajes WebSocket según el tipo."""
        # TODO: Implementar procesamiento específico según el tipo de stream
        # Por ahora, solo log
        self.logger.debug(f"Received WebSocket message for {stream_name}: {data}")
    
    async def check_websocket_health(self) -> Dict[str, bool]:
        """
        Verifica la salud de las conexiones WebSocket.
        
        Returns:
            Dict con estado de cada conexión
        """
        now = time.time()
        health_status = {}
        
        for stream_name, last_ping in self._ws_last_ping.items():
            lag = now - last_ping
            is_healthy = lag < WS_FAIL_SEC
            
            if not is_healthy:
                self.logger.warning(f"WebSocket {stream_name} unhealthy: {lag:.2f}s lag")
            
            health_status[stream_name] = is_healthy
        
        return health_status
    
    async def close_websocket(self, symbol: str, stream_type: str = "bookTicker") -> None:
        """Cierra una conexión WebSocket específica."""
        stream_name = f"{symbol.lower()}@{stream_type}"
        
        if stream_name in self._ws_connections:
            websocket = self._ws_connections[stream_name]
            await websocket.close()
            del self._ws_connections[stream_name]
            del self._ws_last_ping[stream_name]
            WS_CONNECTED.labels(symbol=symbol, type=stream_type).set(0)
            self.logger.info(f"WebSocket closed for {stream_name}")
    
    async def close_all_websockets(self) -> None:
        """Cierra todas las conexiones WebSocket."""
        for stream_name in list(self._ws_connections.keys()):
            symbol, stream_type = stream_name.split("@")
            await self.close_websocket(symbol, stream_type)
