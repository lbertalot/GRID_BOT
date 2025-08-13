import asyncio
import json
import os
import time
from typing import Any, Optional

try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # pragma: no cover - redis opcional
    Redis = None  # type: ignore


class AsyncCache:
    """
    Caché asíncrona con preferencia por Redis y fallback en memoria.
    - Usa TTL en segundos.
    - Serializa dict/list como JSON.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._use_redis = False
        self._redis: Optional[Redis] = None
        self._memory_store: dict[str, tuple[float, str]] = {}

        if redis_url and Redis is not None:
            try:
                self._redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
                self._use_redis = True
            except Exception:
                self._use_redis = False

    async def get(self, key: str) -> Optional[str]:
        if self._use_redis and self._redis is not None:
            try:
                return await self._redis.get(key)
            except Exception:
                # Fallback a memoria si Redis falla
                pass
        # In-memory fallback
        now = time.time()
        item = self._memory_store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < now:
            self._memory_store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        # Serializar
        if isinstance(value, (dict, list)):
            serialized = json.dumps(value)
        else:
            serialized = str(value)

        if self._use_redis and self._redis is not None:
            try:
                await self._redis.set(key, serialized, ex=ttl_seconds)
                return
            except Exception:
                # Fallback a memoria si Redis falla
                pass

        # In-memory fallback
        expires_at = time.time() + max(1, ttl_seconds)
        self._memory_store[key] = (expires_at, serialized)


_global_cache: Optional[AsyncCache] = None


def get_async_cache() -> AsyncCache:
    global _global_cache
    if _global_cache is None:
        redis_url = os.getenv("REDIS_URL") or os.getenv("redis_url") or os.getenv("REDIS_URI")
        _global_cache = AsyncCache(redis_url=redis_url)
    return _global_cache


