#!/usr/bin/env python3
"""
Test para validar la optimización de latencia con Redis Cache
"""

import pytest
import asyncio
import sys
import os
import time

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.redis_cache import RedisCache
from app.services.binance_service import BinanceService


class TestRedisCacheOptimization:
    """Test para validar optimización de latencia con Redis"""
    
    @pytest.fixture
    def redis_cache(self):
        """Fixture para RedisCache"""
        return RedisCache()
    
    @pytest.fixture
    def binance_service(self):
        """Fixture para BinanceService"""
        return BinanceService()
    
    @pytest.mark.asyncio
    async def test_redis_cache_basic_operations(self, redis_cache):
        """Test operaciones básicas de Redis cache"""
        
        # Test set/get
        await redis_cache.set("test_key", "test_value", 60)
        value = await redis_cache.get("test_key")
        assert value == "test_value"
        
        # Test JSON serialization
        test_data = {"symbol": "ETHUSDT", "price": 3000.0, "timestamp": 1234567890}
        await redis_cache.set("test_json", test_data, 60)
        retrieved_data = await redis_cache.get("test_json")
        assert retrieved_data == test_data
        
        # Test exists
        exists = await redis_cache.exists("test_key")
        assert exists is True
        
        # Test delete
        deleted = await redis_cache.delete("test_key")
        assert deleted is True
        
        # Test non-existent key
        value = await redis_cache.get("test_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_symbol_ticker_caching(self, redis_cache):
        """Test cache de ticker de símbolos"""
        
        symbol = "ETHUSDT"
        ticker_data = {
            "symbol": symbol,
            "price": "3000.50",
            "time": 1234567890
        }
        
        # Guardar ticker en cache
        result = await redis_cache.set_symbol_ticker(symbol, ticker_data)
        assert result is True
        
        # Obtener ticker desde cache
        cached_ticker = await redis_cache.get_symbol_ticker(symbol)
        assert cached_ticker == ticker_data
        
        # Verificar que se puede obtener con diferentes casos
        cached_ticker_upper = await redis_cache.get_symbol_ticker("ethusdt")
        assert cached_ticker_upper == ticker_data
    
    @pytest.mark.asyncio
    async def test_exchange_info_caching(self, redis_cache):
        """Test cache de información del exchange"""
        
        exchange_data = {
            "timezone": "UTC",
            "serverTime": 1234567890,
            "symbols": [
                {
                    "symbol": "ETHUSDT",
                    "status": "TRADING",
                    "filters": [
                        {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "1000000.00", "tickSize": "0.01"},
                        {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "9000.00", "stepSize": "0.001"}
                    ]
                }
            ]
        }
        
        # Guardar exchange info
        result = await redis_cache.set_exchange_info(exchange_data)
        assert result is True
        
        # Obtener exchange info
        cached_info = await redis_cache.get_exchange_info()
        assert cached_info == exchange_data
    
    @pytest.mark.asyncio
    async def test_account_info_caching(self, redis_cache):
        """Test cache de información de cuenta"""
        
        account_data = {
            "accountType": "SPOT",
            "balances": [
                {"asset": "USDT", "free": "1000.00", "locked": "0.00"},
                {"asset": "ETH", "free": "0.5", "locked": "0.0"}
            ],
            "permissions": ["SPOT"]
        }
        
        # Guardar account info
        result = await redis_cache.set_account_info(account_data)
        assert result is True
        
        # Obtener account info
        cached_account = await redis_cache.get_account_info()
        assert cached_account == account_data
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, redis_cache):
        """Test estadísticas del cache"""
        
        # Realizar algunas operaciones para generar estadísticas
        await redis_cache.set("key1", "value1", 60)
        await redis_cache.get("key1")  # Hit
        await redis_cache.get("key2")  # Miss
        
        stats = await redis_cache.get_cache_stats()
        
        # Verificar que las estadísticas están presentes
        assert 'cache_hits' in stats
        assert 'cache_misses' in stats
        assert 'hit_rate_percent' in stats
        
        print(f"📊 Estadísticas de cache:")
        print(f"  - Hits: {stats['cache_hits']}")
        print(f"  - Misses: {stats['cache_misses']}")
        print(f"  - Hit Rate: {stats['hit_rate_percent']}%")
    
    @pytest.mark.asyncio
    async def test_symbol_invalidation(self, redis_cache):
        """Test invalidación de cache por símbolo"""
        
        symbol = "ETHUSDT"
        
        # Guardar datos para el símbolo
        await redis_cache.set_symbol_ticker(symbol, {"price": "3000.0"})
        await redis_cache.set(f"exchange_info:{symbol}", {"filters": []})
        await redis_cache.set(f"klines:{symbol}:1m:100", [])
        
        # Verificar que existen
        assert await redis_cache.exists(f"ticker:{symbol}")
        assert await redis_cache.exists(f"exchange_info:{symbol}")
        
        # Invalidar símbolo
        await redis_cache.invalidate_symbol(symbol)
        
        # Verificar que se eliminaron
        assert not await redis_cache.exists(f"ticker:{symbol}")
        assert not await redis_cache.exists(f"exchange_info:{symbol}")
    
    @pytest.mark.asyncio
    async def test_ttl_configuration(self, redis_cache):
        """Test que los TTL están configurados correctamente"""
        
        ttl_config = redis_cache.ttl_config
        
        # Verificar que todos los TTL están definidos
        expected_keys = ['exchange_info', 'symbol_ticker', 'klines', 'account_info', 'order_book', 'market_data']
        for key in expected_keys:
            assert key in ttl_config
            assert ttl_config[key] > 0
        
        # Verificar que los valores son razonables
        assert ttl_config['exchange_info'] >= 3600  # Al menos 1 hora
        assert ttl_config['symbol_ticker'] <= 10    # Máximo 10 segundos
        assert ttl_config['klines'] <= 60           # Máximo 1 minuto
        assert ttl_config['account_info'] <= 30     # Máximo 30 segundos
        
        print(f"📋 Configuración de TTL:")
        for key, value in ttl_config.items():
            print(f"  - {key}: {value}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
