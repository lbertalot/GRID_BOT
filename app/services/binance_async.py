import asyncio
import json
import math
import os
import random
import time
from typing import Any, Dict, Optional

from binance.client import Client
from binance.exceptions import BinanceAPIException

from app.services.cache import get_async_cache


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
        api_key = os.getenv("BINANCE_API_KEY") or os.getenv("BINANCE_API_SECRET")
        api_secret = os.getenv("BINANCE_API_SECRET") or os.getenv("BINANCE_SECRET_KEY")
        testnet = (os.getenv("BINANCE_TESTNET", "false").lower() == "true")
        self.client = Client(api_key, api_secret, testnet=testnet)
        self.cache = get_async_cache()
        self.ttl = ttl_seconds
        self.price_rl = RateLimiter(rate_per_sec, burst)
        self.klines_rl = RateLimiter(rate_per_sec, burst)

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


