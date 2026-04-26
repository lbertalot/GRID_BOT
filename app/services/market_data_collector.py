"""
Market Data Collector

Responsable de:
- Obtener velas (klines) y métricas básicas desde Binance con backoff y rate limiting
- Cachear respuestas en Redis/memoria (TTL 5s)
- Validar y ajustar cantidad/precio a stepSize/tickSize antes de operar
- Guardar datos de klines en PostgreSQL (tabla klines_data)

Compatibilidad:
- Modo paper trading respetado (solo lectura de mercado)
- Evitar bloqueos del loop usando asyncio.to_thread / cliente async wrapper
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

from app.services.binance_async import AsyncBinanceWrapper
from app.services.cache import get_async_cache
from app.services.order_validation import OrderValidator
from binance.client import Client


logger = logging.getLogger(__name__)


class MarketDataCollector:
    """Colector de datos de mercado con caché y backoff."""

    def __init__(self, ttl_seconds: int = 5):
        self.ttl_seconds = ttl_seconds
        self.cache = get_async_cache()
        self.binance = AsyncBinanceWrapper(ttl_seconds=ttl_seconds)
        # Cliente sync solo para metadata/validación (usado en to_thread) - inicialización lazy
        self._client = None
        self._validator = None
        self._db_url = os.getenv(
            "DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot"
        )

    async def _ensure_client(self):
        """
        Inicializa el cliente de Binance de forma lazy (solo cuando se necesita).

        ✅ Bug #3 Fix: Inicialización envuelta en asyncio.to_thread() para no bloquear event loop
        """
        if self._client is None:

            def _init():
                api_key = os.getenv("BINANCE_API_KEY") or os.getenv(
                    "BINANCE_SECRET_KEY"
                )
                api_secret = os.getenv("BINANCE_SECRET_KEY")
                # Forzar testnet=false para producción - resolver errores -2015
                client = Client(api_key, api_secret, testnet=False)
                validator = OrderValidator(client)
                return client, validator

            # ✅ FIX: Ejecutar inicialización en thread separado
            self._client, self._validator = await asyncio.to_thread(_init)
            logger.debug("✅ Binance client inicializado (async)")

        return self._client

    async def get_price(self, symbol: str) -> float:
        """Obtiene precio con caché TTL 5s y backoff."""
        return await self.binance.get_price(symbol)

    async def get_klines(
        self, symbol: str, interval: str = "1m", limit: int = 120
    ) -> List[List[Any]]:
        """Obtiene klines con caché TTL 5s y backoff."""
        return await self.binance.get_klines(symbol, interval, limit)

    async def validate_order(
        self,
        symbol: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Valida y ajusta cantidad/precio usando reglas de Binance (stepSize/tickSize/minNotional).

        ✅ Bug #3 Fix: Validación envuelta en asyncio.to_thread()
        """
        await (
            self._ensure_client()
        )  # Inicializar cliente lazy si aún no existe (ahora es async)

        # ✅ FIX: Ejecutar validación en thread separado
        return await asyncio.to_thread(
            self._validator.validate_order_parameters,
            symbol,
            quantity,
            "BUY",
            order_type,
            price,
        )  # side no afecta validación de cantidades

    async def save_klines_to_db(
        self, symbol: str, interval: str, klines: List[List[Any]]
    ) -> int:
        """Guarda klines en tabla klines_data (crea si no existe). Retorna filas insertadas."""
        if not klines:
            return 0
        conn: Optional[asyncpg.Connection] = None
        try:
            conn = await asyncpg.connect(self._db_url)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS klines_data (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    interval VARCHAR(10) NOT NULL,
                    open_time TIMESTAMP NOT NULL,
                    open_price DECIMAL(20, 8) NOT NULL,
                    high_price DECIMAL(20, 8) NOT NULL,
                    low_price DECIMAL(20, 8) NOT NULL,
                    close_price DECIMAL(20, 8) NOT NULL,
                    volume DECIMAL(20, 8) NOT NULL,
                    close_time TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Limpiar ventana de datos superpuestos (mismo symbol/interval en el rango)
            first_open = datetime.fromtimestamp(klines[0][0] / 1000)
            last_close = datetime.fromtimestamp(klines[-1][6] / 1000)
            await conn.execute(
                """
                DELETE FROM klines_data WHERE symbol=$1 AND interval=$2 AND open_time BETWEEN $3 AND $4
                """,
                symbol,
                interval,
                first_open,
                last_close,
            )

            inserted = 0
            for k in klines:
                await conn.execute(
                    """
                    INSERT INTO klines_data (symbol, interval, open_time, open_price, high_price, low_price, close_price, volume, close_time)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    symbol,
                    interval,
                    datetime.fromtimestamp(k[0] / 1000),
                    float(k[1]),
                    float(k[2]),
                    float(k[3]),
                    float(k[4]),
                    float(k[5]),
                    datetime.fromtimestamp(k[6] / 1000),
                )
                inserted += 1
            return inserted
        except Exception as e:
            logger.error(f"Error guardando klines en BD: {e}")
            return 0
        finally:
            if conn:
                await conn.close()


# Instancia global opcional (evitar efectos en exportación de OpenAPI/CI)
if os.getenv("EXPORT_OPENAPI", "0") != "1":
    market_data_collector = MarketDataCollector()
