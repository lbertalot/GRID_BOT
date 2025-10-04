import asyncio
import json
import math
import os
import random
import time
from typing import Any, Dict, Optional

USE_REAL = os.getenv("USE_REAL_BINANCE", "0") == "1"
if not USE_REAL:
    class _DummyClient:
        def get_symbol_ticker(self, symbol: str):
            return {"symbol": symbol, "price": "100.0"}
        def get_klines(self, symbol: str, interval: str, limit: int = 100):
            now = int(time.time() * 1000)
            out = []
            for i in range(limit):
                open_time = now - (limit - i) * 60_000
                close_time = open_time + 60_000
                o = 100.0 + i
                h = o * 1.01
                l = o * 0.99
                c = o * 1.005
                v = 10 + i
                out.append([open_time, str(o), str(h), str(l), str(c), str(v), close_time])
            return out
        def create_order(self, **kwargs):
            return {"orderId": int(time.time() * 1000), "status": "FILLED"}
    class _DummyException(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args)
    Client = _DummyClient  # type: ignore
    BinanceAPIException = _DummyException  # type: ignore
else:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException

from app.services.cache import get_async_cache
from app.services.order_validation import OrderValidator


class RateLimiter:
    """Rate limiter sencillo (token bucket) por clave.
    - rate: tokens por segundo
    - burst: capacidad máxima del bucket
    """

    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.timestamp = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.time()
            elapsed = now - self.timestamp
            self.timestamp = now
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class AsyncBinanceWrapper:
    """
    Wrapper asíncrono para python-binance (cliente sync), con:
    - Encapsulado en asyncio.to_thread para no bloquear
    - Caché (Redis/memoria) de precios y klines
    - Rate limiting + backoff exponencial
    """

    def __init__(self, *, ttl_seconds: int = 5, rate_per_sec: float = 5.0, burst: int = 10):
        if USE_REAL:
            api_key = os.getenv("BINANCE_API_KEY") or os.getenv("BINANCE_SECRET_KEY")
            api_secret = os.getenv("BINANCE_SECRET_KEY")
            testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
            self.client = Client(api_key, api_secret, testnet=testnet)
        else:
            self.client = Client()
        self.cache = get_async_cache()
        self.ttl = ttl_seconds
        self.price_rl = RateLimiter(rate_per_sec, burst)
        self.klines_rl = RateLimiter(rate_per_sec, burst)
        # Validador de órdenes (ajuste step/tick/minNotional)
        self.validator = OrderValidator(self.client)

    async def _with_backoff(self, coro_func, *args, **kwargs):
        delay = 0.5
        for attempt in range(5):
            try:
                return await coro_func(*args, **kwargs)
            except BinanceAPIException as e:
                # Retry en errores de rate limit o temporales
                if getattr(e, 'code', None) in (-1003, -1015) or 429 in [getattr(e, 'status_code', None)]:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 8.0)
                    continue
                raise
            except Exception as e:
                # Errores transitorios de red (socket/timeout)
                if any(s in str(e).lower() for s in ["timed out", "temporarily unavailable", "connection reset", "network is unreachable", "read timeout", "write timeout"]):
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 8.0)
                    continue
                raise

    async def get_price(self, symbol: str) -> float:
        key = f"price:{symbol.upper()}"
        cached = await self.cache.get(key)
        if cached:
            try:
                return float(cached)
            except Exception:
                pass

        await self.price_rl.acquire()

        async def _call():
            return await asyncio.to_thread(lambda: float(self.client.get_symbol_ticker(symbol=symbol.upper())["price"]))

        price = await self._with_backoff(_call)
        await self.cache.set(key, str(price), self.ttl)
        return price

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list[list[Any]]:
        key = f"klines:{symbol.upper()}:{interval}:{limit}"
        cached = await self.cache.get(key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        await self.klines_rl.acquire()

        async def _call():
            return await asyncio.to_thread(lambda: self.client.get_klines(symbol=symbol.upper(), interval=interval, limit=limit))

        kl = await self._with_backoff(_call)
        await self.cache.set(key, kl, self.ttl)
        return kl

    async def create_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        """Crea una orden de mercado aplicando validación de cantidad/precio.
        - Ajusta cantidad a stepSize
        - Usa backoff ante errores 429/-1003/-1015
        - Ejecuta en to_thread para no bloquear
        """
        # Validación/ajuste
        validation = await asyncio.to_thread(self.validator.validate_order_parameters, symbol, quantity, side, 'MARKET')
        if not validation.get('is_valid', False):
            # Levantar error con detalles de validación
            errors = " | ".join(validation.get('errors') or [])
            raise ValueError(f"Parámetros inválidos: {errors}")
        adjusted_qty = float(validation['quantity_info']['adjusted_quantity'])

        async def _call():
            def _do():
                return self.client.create_order(
                    symbol=symbol.upper(),
                    side=side.upper(),
                    type='MARKET',
                    quantity=adjusted_qty
                )
            return await asyncio.to_thread(_do)

        return await self._with_backoff(_call)


