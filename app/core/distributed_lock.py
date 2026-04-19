"""
Distributed Lock usando Redis para prevenir ejecuciones concurrentes de Celery tasks

Uso:
    @with_distributed_lock("my_critical_task", timeout=300, blocking=False)
    def my_task():
        # Solo se ejecuta una instancia a la vez
        pass
"""
import logging
import os
import time
from functools import wraps
from typing import Optional, Callable, Any, Dict
from redis import Redis
from redis.lock import Lock as RedisLock
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# Import metrics (with try/except for graceful degradation)
try:
    from app.core.metrics import (
        distributed_lock_acquired_total,
        distributed_lock_skipped_total,
        distributed_lock_errors_total,
        distributed_lock_duration_seconds
    )
    METRICS_AVAILABLE = True
except ImportError:
    logger.warning("Prometheus metrics not available for distributed_lock")
    METRICS_AVAILABLE = False

# Cliente Redis singleton
_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """
    Obtener cliente Redis singleton
    
    Returns:
        Cliente Redis configurado
    """
    global _redis_client
    if _redis_client is None:
        # Default 127.0.0.1: pytest y FastAPI en el host sin Docker. En Compose,
        # define REDIS_URL=redis://redis:6379/0 (o el que use tu stack) en .env.
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        url_source = "REDIS_URL" if "REDIS_URL" in os.environ else "default(localhost)"
        try:
            _redis_client = Redis.from_url(
                redis_url,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            _redis_client.ping()
            logger.info(
                "Redis client listo para distributed locks (url=%s, source=%s)",
                redis_url,
                url_source,
            )
        except RedisError as e:
            logger.error(f"❌ Error conectando a Redis: {e}")
            raise
    return _redis_client


def reset_redis_client() -> None:
    """
    Descarta el cliente Redis singleton.

    Uso típico: tests (fixture) para forzar nueva conexión tras cambiar REDIS_URL,
    o depuración. En producción no suele hacer falta llamarla.
    """
    global _redis_client
    _redis_client = None


def with_distributed_lock(
    lock_name: str,
    timeout: int = 300,
    blocking: bool = False,
    blocking_timeout: Optional[int] = None
):
    """
    Decorador para funciones que requieren lock distribuido (evita ejecuciones concurrentes)
    
    Args:
        lock_name: Nombre único del lock (ej: "trading_cycle", "rebalancing")
        timeout: Timeout en segundos (máximo tiempo que puede durar la función)
        blocking: Si True, espera a que se libere el lock. Si False, retorna inmediatamente
        blocking_timeout: Timeout en segundos para esperar el lock (solo si blocking=True)
    
    Returns:
        Decorador que aplica el lock distribuido
    
    Example:
        @with_distributed_lock("trading_cycle", timeout=300, blocking=False)
        def trading_cycle_tick():
            # Si otro worker ya está ejecutando, esta llamada se omite
            perform_trading()
    
    Behavior:
        - Si blocking=False: Retorna {"status": "skipped"} si lock está tomado
        - Si blocking=True: Espera hasta blocking_timeout segundos a que se libere
        - Lock se libera automáticamente después de timeout segundos (safety)
        - Lock se libera inmediatamente al terminar la función (normal)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                redis_client = get_redis_client()
            except RedisError as e:
                logger.error(
                    f"❌ No se pudo conectar a Redis para lock '{lock_name}': {e}. "
                    f"Ejecutando sin lock (modo degradado)"
                )
                # En modo degradado, ejecutar sin lock
                return func(*args, **kwargs)
            
            lock_key = f"lock:celery:{lock_name}"
            lock: Optional[RedisLock] = None
            
            try:
                # Crear lock
                lock = redis_client.lock(
                    name=lock_key,
                    timeout=timeout,  # Auto-release después de timeout segundos
                    blocking=blocking,
                    blocking_timeout=blocking_timeout
                )
                
                # Intentar adquirir lock
                acquired = lock.acquire(blocking=blocking, blocking_timeout=blocking_timeout)
                
                if not acquired:
                    # Métrica: Lock omitido
                    if METRICS_AVAILABLE:
                        try:
                            distributed_lock_skipped_total.labels(
                                lock_name=lock_name,
                                function=func.__name__
                            ).inc()
                        except Exception:
                            pass
                    
                    logger.warning(
                        f"🔒 Lock '{lock_name}' ya está tomado por otro worker. "
                        f"Omitiendo ejecución de {func.__name__}"
                    )
                    return {
                        "status": "skipped",
                        "reason": "lock_held",
                        "lock_name": lock_name,
                        "function": func.__name__
                    }
                
                # Métrica: Lock adquirido
                if METRICS_AVAILABLE:
                    try:
                        distributed_lock_acquired_total.labels(lock_name=lock_name).inc()
                    except Exception:
                        pass
                
                logger.info(
                    f"🔓 Lock '{lock_name}' adquirido exitosamente. "
                    f"Ejecutando {func.__name__} (timeout: {timeout}s)"
                )
                
                # Ejecutar función con lock activo
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    
                    # Métrica: Duración del lock
                    if METRICS_AVAILABLE:
                        try:
                            duration = time.time() - start_time
                            distributed_lock_duration_seconds.labels(lock_name=lock_name).observe(duration)
                        except Exception:
                            pass
                    
                    logger.info(
                        f"✅ Función {func.__name__} completada exitosamente. "
                        f"Liberando lock '{lock_name}'"
                    )
                    return result
                    
                except Exception as e:
                    # Métrica: Error en función con lock
                    if METRICS_AVAILABLE:
                        try:
                            distributed_lock_errors_total.labels(
                                lock_name=lock_name,
                                error_type=type(e).__name__
                            ).inc()
                        except Exception:
                            pass
                    
                    logger.error(
                        f"❌ Error ejecutando {func.__name__} con lock '{lock_name}': {e}"
                    )
                    raise
                    
            except RedisError as e:
                logger.error(
                    f"❌ Error de Redis con lock '{lock_name}': {e}. "
                    f"Ejecutando sin lock (modo degradado)"
                )
                # En caso de error de Redis, ejecutar sin lock
                return func(*args, **kwargs)
                
            finally:
                # Liberar lock si fue adquirido
                if lock is not None:
                    try:
                        # Verificar si este proceso tiene el lock antes de liberar
                        if lock.owned():
                            lock.release()
                            logger.debug(f"🔓 Lock '{lock_name}' liberado")
                    except RedisError as e:
                        logger.error(
                            f"⚠️ Error liberando lock '{lock_name}': {e}. "
                            f"Lock se auto-liberará en {timeout}s"
                        )
        
        return wrapper
    return decorator


def check_lock_status(lock_name: str) -> Dict[str, Any]:
    """
    Verificar el estado de un lock
    
    Args:
        lock_name: Nombre del lock a verificar
    
    Returns:
        Dict con información del lock
    """
    try:
        redis_client = get_redis_client()
        lock_key = f"lock:celery:{lock_name}"
        
        # Verificar si el lock existe
        exists = redis_client.exists(lock_key)
        
        if exists:
            # Obtener TTL (tiempo restante)
            ttl = redis_client.ttl(lock_key)
            return {
                "lock_name": lock_name,
                "status": "locked",
                "ttl_seconds": ttl if ttl > 0 else None
            }
        else:
            return {
                "lock_name": lock_name,
                "status": "free"
            }
            
    except RedisError as e:
        logger.error(f"❌ Error verificando lock '{lock_name}': {e}")
        return {
            "lock_name": lock_name,
            "status": "error",
            "error": str(e)
        }


def force_release_lock(lock_name: str) -> bool:
    """
    Liberar un lock manualmente (usar con precaución!)
    
    Args:
        lock_name: Nombre del lock a liberar
    
    Returns:
        True si se liberó, False si no existía
    """
    try:
        redis_client = get_redis_client()
        lock_key = f"lock:celery:{lock_name}"
        
        deleted = redis_client.delete(lock_key)
        
        if deleted:
            logger.warning(f"⚠️ Lock '{lock_name}' liberado forzosamente")
            return True
        else:
            logger.info(f"ℹ️ Lock '{lock_name}' no existía")
            return False
            
    except RedisError as e:
        logger.error(f"❌ Error liberando lock '{lock_name}': {e}")
        return False

