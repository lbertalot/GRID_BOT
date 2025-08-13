import asyncio
import os
import sys
import pytest

# Asegurar que el path del proyecto esté en PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.cache import AsyncCache


@pytest.mark.asyncio
async def test_async_cache_memory_fallback(monkeypatch):
    # Forzar sin Redis
    monkeypatch.delenv("REDIS_URL", raising=False)
    cache = AsyncCache(redis_url=None)
    await cache.set("price:BTCUSDT", "50000", ttl_seconds=1)
    v = await cache.get("price:BTCUSDT")
    assert v == "50000"
    await asyncio.sleep(1.1)
    assert await cache.get("price:BTCUSDT") is None


