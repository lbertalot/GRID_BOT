#!/usr/bin/env python3
"""
Script para inicializar la base de datos de GridBot
"""

import asyncio
import asyncpg
import logging
from datetime import datetime
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://griduser:gridpass@db:5432/gridbot")

# SQL para crear las tablas
CREATE_TABLES_SQL = """
-- Tabla de configuración del grid
CREATE TABLE IF NOT EXISTS grid_config (
    id SERIAL PRIMARY KEY,
    trading_pair VARCHAR(20) NOT NULL,
    grid_levels INTEGER NOT NULL DEFAULT 10,
    min_price DECIMAL(20, 8) NOT NULL,
    max_price DECIMAL(20, 8) NOT NULL,
    quantity_per_trade DECIMAL(20, 8) NOT NULL,
    auto_rebalance BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de límites de activos
CREATE TABLE IF NOT EXISTS asset_limits (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    min_qty DECIMAL(20, 8) NOT NULL,
    max_qty DECIMAL(20, 8) NOT NULL,
    step_size DECIMAL(20, 8) NOT NULL,
    tick_size DECIMAL(20, 8) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de operaciones de trading
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL, -- 'BUY' or 'SELL'
    quantity DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    profit_loss DECIMAL(20, 8),
    status VARCHAR(20) DEFAULT 'PENDING', -- 'PENDING', 'FILLED', 'CANCELLED'
    order_id VARCHAR(100),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    grid_level INTEGER,
    strategy VARCHAR(50) DEFAULT 'GRID'
);

-- Tabla de métricas de rendimiento
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_profit DECIMAL(20, 8) DEFAULT 0,
    total_loss DECIMAL(20, 8) DEFAULT 0,
    win_rate DECIMAL(5, 2) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 4) DEFAULT 0,
    max_drawdown DECIMAL(10, 4) DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de alertas
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL, -- 'PROFIT', 'LOSS', 'SYSTEM', 'ERROR'
    message TEXT NOT NULL,
    level VARCHAR(20) DEFAULT 'INFO', -- 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    sent_to_telegram BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de configuración del sistema
CREATE TABLE IF NOT EXISTS system_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar el rendimiento
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(type);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
"""

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
        
        logger.info("Creando tablas...")
        await conn.execute(CREATE_TABLES_SQL)
        
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