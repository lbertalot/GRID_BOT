"""
Utilidades de performance optimizadas
Siguiendo mejores prácticas de FastAPI y asyncio
"""

import asyncio
import functools
from typing import Any, Callable, Dict, Optional, TypeVar, List
from contextlib import asynccontextmanager
import asyncpg
import os

T = TypeVar("T")


# Cache en memoria con TTL
class MemoryCache:
    """Cache simple en memoria con TTL"""

    def __init__(self):
        self._cache: Dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, expiry = self._cache[key]
            if asyncio.get_event_loop().time() < expiry:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: float = 300):
        expiry = asyncio.get_event_loop().time() + ttl
        self._cache[key] = (value, expiry)

    def clear(self):
        self._cache.clear()


# Cache global
_memory_cache = MemoryCache()


def cached(ttl: float = 300):
    """Decorador para cachear resultados de funciones"""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Crear clave única para la función y argumentos
            key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"

            # Intentar obtener del cache
            cached_result = _memory_cache.get(key)
            if cached_result is not None:
                return cached_result

            # Ejecutar función y cachear resultado
            result = await func(*args, **kwargs)
            _memory_cache.set(key, result, ttl)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"

            cached_result = _memory_cache.get(key)
            if cached_result is not None:
                return cached_result

            result = func(*args, **kwargs)
            _memory_cache.set(key, result, ttl)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Connection pooling para PostgreSQL
_db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """Obtiene el pool de conexiones a la base de datos"""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"),
            min_size=5,
            max_size=20,
            command_timeout=60,
        )
    return _db_pool


@asynccontextmanager
async def get_db_connection():
    """Context manager para obtener conexión de la base de datos"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn


# Rate limiting funcional
class RateLimiter:
    """Rate limiter funcional"""

    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: List[float] = []

    async def acquire(self) -> bool:
        """Intenta adquirir un slot de rate limit"""
        now = asyncio.get_event_loop().time()

        # Limpiar llamadas antiguas
        self.calls = [
            call_time for call_time in self.calls if now - call_time < self.time_window
        ]

        if len(self.calls) >= self.max_calls:
            return False

        self.calls.append(now)
        return True


# Lazy loading para datos pesados
class LazyLoader:
    """Cargador lazy para datos pesados"""

    def __init__(self, loader_func: Callable[[], Any]):
        self.loader_func = loader_func
        self._data: Optional[Any] = None
        self._loaded = False

    async def get_data(self) -> Any:
        """Obtiene los datos, cargándolos si es necesario"""
        if not self._loaded:
            self._data = await self.loader_func()
            self._loaded = True
        return self._data

    def reset(self):
        """Resetea el loader para forzar recarga"""
        self._data = None
        self._loaded = False


# Optimización de consultas
async def batch_query(queries: List[Callable], batch_size: int = 10) -> List[Any]:
    """Ejecuta consultas en lotes para optimizar performance"""
    results = []

    for i in range(0, len(queries), batch_size):
        batch = queries[i : i + batch_size]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)
        results.extend(batch_results)

    return results


# Decorador para medir performance
def measure_performance(func: Callable[..., T]) -> Callable[..., T]:
    """Decorador para medir tiempo de ejecución"""

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> T:
        start_time = asyncio.get_event_loop().time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            end_time = asyncio.get_event_loop().time()
            print(f"{func.__name__} ejecutado en {end_time - start_time:.4f} segundos")

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs) -> T:
        start_time = asyncio.get_event_loop().time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = asyncio.get_event_loop().time()
            print(f"{func.__name__} ejecutado en {end_time - start_time:.4f} segundos")

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
