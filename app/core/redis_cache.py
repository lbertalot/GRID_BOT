"""
Redis Cache - Sistema de cache optimizado para reducir latencia de API
GridBot v2.5 - Optimización de rendimiento
"""

import json
import logging
import asyncio
import redis.asyncio as redis
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Sistema de cache Redis optimizado para GridBot v2.5
    Reduce latencia de API mediante cache inteligente
    """
    
    def __init__(self, 
                 host: str = "redis",
                 port: int = 6379,
                 db: int = 0,
                 password: Optional[str] = None,
                 decode_responses: bool = True):
        
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.decode_responses = decode_responses
        
        # Configuración de TTL por tipo de dato
        self.ttl_config = {
            'exchange_info': 3600,      # 1 hora - información del exchange cambia poco
            'symbol_ticker': 5,         # 5 segundos - precios cambian frecuentemente
            'klines': 30,               # 30 segundos - datos históricos
            'account_info': 10,         # 10 segundos - balance cambia con trades
            'order_book': 1,            # 1 segundo - order book cambia muy rápido
            'market_data': 15,          # 15 segundos - datos de mercado generales
        }
        
        self._redis_client = None
        self.logger = logger
        
        # Métricas de cache
        self.cache_hits = 0
        self.cache_misses = 0
        
        self.logger.info("🔄 Redis Cache inicializado")
    
    async def _get_client(self) -> redis.Redis:
        """Obtener cliente Redis (lazy initialization)"""
        if self._redis_client is None:
            try:
                self._redis_client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=self.decode_responses,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                
                # Test de conexión
                await self._redis_client.ping()
                self.logger.info("✅ Conexión Redis establecida")
                
            except Exception as e:
                self.logger.error(f"❌ Error conectando a Redis: {e}")
                raise
        
        return self._redis_client
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Obtener valor del cache
        
        Args:
            key: Clave del cache
            
        Returns:
            Valor cacheado o None si no existe
        """
        try:
            client = await self._get_client()
            value = await client.get(key)
            
            if value is not None:
                self.cache_hits += 1
                try:
                    # Intentar deserializar JSON
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # Si no es JSON, devolver como string
                    return value
            else:
                self.cache_misses += 1
                return None
                
        except Exception as e:
            self.logger.error(f"Error obteniendo cache {key}: {e}")
            self.cache_misses += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Establecer valor en cache
        
        Args:
            key: Clave del cache
            value: Valor a cachear
            ttl: Time to live en segundos (opcional)
            
        Returns:
            True si se guardó correctamente
        """
        try:
            client = await self._get_client()
            
            # Serializar valor
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
            
            # Establecer con TTL
            if ttl:
                await client.setex(key, ttl, serialized_value)
            else:
                await client.set(key, serialized_value)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error estableciendo cache {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Eliminar clave del cache"""
        try:
            client = await self._get_client()
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            self.logger.error(f"Error eliminando cache {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Verificar si una clave existe en cache"""
        try:
            client = await self._get_client()
            result = await client.exists(key)
            return result > 0
        except Exception as e:
            self.logger.error(f"Error verificando existencia {key}: {e}")
            return False
    
    async def get_exchange_info(self, symbol: str = None) -> Optional[Dict]:
        """
        Obtener información del exchange desde cache
        
        Args:
            symbol: Símbolo específico (opcional)
            
        Returns:
            Información del exchange o None
        """
        if symbol:
            key = f"exchange_info:{symbol.upper()}"
        else:
            key = "exchange_info:all"
        
        return await self.get(key)
    
    async def set_exchange_info(self, data: Dict, symbol: str = None) -> bool:
        """
        Guardar información del exchange en cache
        
        Args:
            data: Datos del exchange
            symbol: Símbolo específico (opcional)
            
        Returns:
            True si se guardó correctamente
        """
        if symbol:
            key = f"exchange_info:{symbol.upper()}"
        else:
            key = "exchange_info:all"
        
        ttl = self.ttl_config['exchange_info']
        return await self.set(key, data, ttl)
    
    async def get_symbol_ticker(self, symbol: str) -> Optional[Dict]:
        """Obtener ticker de símbolo desde cache"""
        key = f"ticker:{symbol.upper()}"
        return await self.get(key)
    
    async def set_symbol_ticker(self, symbol: str, data: Dict) -> bool:
        """Guardar ticker de símbolo en cache"""
        key = f"ticker:{symbol.upper()}"
        ttl = self.ttl_config['symbol_ticker']
        return await self.set(key, data, ttl)
    
    async def get_account_info(self) -> Optional[Dict]:
        """Obtener información de cuenta desde cache"""
        key = "account_info"
        return await self.get(key)
    
    async def set_account_info(self, data: Dict) -> bool:
        """Guardar información de cuenta en cache"""
        key = "account_info"
        ttl = self.ttl_config['account_info']
        return await self.set(key, data, ttl)
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> Optional[list]:
        """Obtener klines desde cache"""
        key = f"klines:{symbol.upper()}:{interval}:{limit}"
        return await self.get(key)
    
    async def set_klines(self, symbol: str, interval: str, data: list, limit: int = 100) -> bool:
        """Guardar klines en cache"""
        key = f"klines:{symbol.upper()}:{interval}:{limit}"
        ttl = self.ttl_config['klines']
        return await self.set(key, data, ttl)
    
    async def invalidate_symbol(self, symbol: str):
        """Invalidar cache de un símbolo específico"""
        patterns = [
            f"ticker:{symbol.upper()}",
            f"exchange_info:{symbol.upper()}",
            f"klines:{symbol.upper()}:*",
            f"order_book:{symbol.upper()}:*"
        ]
        
        try:
            client = await self._get_client()
            for pattern in patterns:
                if '*' in pattern:
                    # Usar SCAN para encontrar claves con patrón
                    async for key in client.scan_iter(match=pattern):
                        await client.delete(key)
                else:
                    await client.delete(pattern)
            
            self.logger.info(f"🗑️ Cache invalidado para {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error invalidando cache {symbol}: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache"""
        try:
            client = await self._get_client()
            info = await client.info('memory')
            
            total_requests = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'hit_rate_percent': round(hit_rate, 2),
                'redis_memory_used': info.get('used_memory_human', 'N/A'),
                'redis_connected_clients': info.get('connected_clients', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas: {e}")
            return {
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'hit_rate_percent': 0,
                'error': str(e)
            }
    
    async def clear_all(self) -> bool:
        """Limpiar todo el cache"""
        try:
            client = await self._get_client()
            await client.flushdb()
            self.logger.info("🗑️ Cache Redis limpiado completamente")
            return True
        except Exception as e:
            self.logger.error(f"Error limpiando cache: {e}")
            return False
    
    async def close(self):
        """Cerrar conexión Redis"""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
            self.logger.info("🔌 Conexión Redis cerrada")


# Instancia global para uso en el sistema
redis_cache = RedisCache()
