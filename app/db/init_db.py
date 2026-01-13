#!/usr/bin/env python3
"""
Script para inicializar la base de datos de GridBot
"""

import asyncio
from sqlalchemy import create_engine, text
import asyncpg
import logging
from datetime import datetime
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot")

# Convertir formato postgres:// a postgresql:// (Heroku usa postgres://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQL manual removido: ahora se usa Alembic como única fuente de verdad para el esquema
CREATE_TABLES_SQL = """-- handled by Alembic migrations"""

# SQL para insertar datos iniciales
INSERT_INITIAL_DATA_SQL = """
-- Insertar configuración inicial del grid
INSERT INTO grid_config (trading_pair, grid_levels, min_price, max_price, quantity_per_trade, auto_rebalance)
VALUES ('BTCUSDT', 10, 45000.0, 55000.0, 0.001, TRUE)
ON CONFLICT DO NOTHING;

-- Insertar límites de activos para BTC
INSERT INTO asset_limits (symbol, min_qty, max_qty, step_size, tick_size)
VALUES ('BTCUSDT', 0.00001, 1000.0, 0.00001, 0.1)
ON CONFLICT DO NOTHING;

-- Insertar configuración del sistema
INSERT INTO system_config (key, value, description) VALUES
('max_daily_loss', '5.0', 'Pérdida máxima diaria en porcentaje'),
('stop_loss', '10.0', 'Stop loss en porcentaje'),
('max_position_size', '20.0', 'Tamaño máximo de posición en porcentaje'),
('trading_enabled', 'true', 'Habilitar/deshabilitar trading'),
('telegram_notifications', 'true', 'Habilitar notificaciones de Telegram')
ON CONFLICT (key) DO NOTHING;

-- Insertar métricas iniciales
INSERT INTO performance_metrics (total_trades, winning_trades, losing_trades, total_profit, total_loss, win_rate)
VALUES (0, 0, 0, 0.0, 0.0, 0.0)
ON CONFLICT DO NOTHING;
"""

async def init_database():
    """Inicializar la base de datos"""
    try:
        logger.info("Conectando a la base de datos...")
        conn = await asyncpg.connect(DATABASE_URL)
        
        logger.info("Esquema gestionado por Alembic. Omitiendo creación manual de tablas.")
        
        logger.info("Insertando datos iniciales...")
        await conn.execute(INSERT_INITIAL_DATA_SQL)
        
        logger.info("Verificando tablas creadas...")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('grid_config', 'asset_limits', 'trades', 'performance_metrics', 'alerts', 'system_config')
        """)
        
        logger.info(f"Tablas creadas: {[table['table_name'] for table in tables]}")
        
        await conn.close()
        logger.info("Base de datos inicializada correctamente")
        
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        raise

def init_db() -> bool:
    """Wrapper síncrono para crear tablas mínimas en contextos sync (tests/app startup)."""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        # Ejecutar el SQL de creación mínimo vía asyncpg es complejo en sync; crear tablas clave mínimas aquí
        # Se confía en rutas de sincronización para completar asset_limits.
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    quantity DECIMAL(20, 8) NOT NULL,
                    entry_price DECIMAL(20, 8) NOT NULL,
                    exit_price DECIMAL(20, 8),
                    profit_loss DECIMAL(20, 8),
                    status VARCHAR(20) DEFAULT 'PENDING',
                    order_id VARCHAR(100),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        return True
    except Exception as e:
        logger.error(f"init_db() fallo: {e}")
        return False

async def check_database_connection():
    """Verificar conexión a la base de datos"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("SELECT 1")
        await conn.close()
        logger.info("Conexión a la base de datos exitosa")
        return True
    except Exception as e:
        logger.error(f"Error conectando a la base de datos: {e}")
        return False

async def main():
    """Función principal"""
    logger.info("Iniciando inicialización de base de datos...")
    
    # Esperar a que la base de datos esté disponible
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        if await check_database_connection():
            break
        retry_count += 1
        logger.info(f"Reintentando conexión... ({retry_count}/{max_retries})")
        await asyncio.sleep(2)
    
    if retry_count >= max_retries:
        logger.error("No se pudo conectar a la base de datos después de múltiples intentos")
        return
    
    # Inicializar base de datos
    await init_database()

if __name__ == "__main__":
    asyncio.run(main()) 