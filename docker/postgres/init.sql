-- Inicialización de la base de datos GridBot
-- Este script se ejecuta automáticamente al crear el contenedor

-- Crear extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Crear esquema para la aplicación
CREATE SCHEMA IF NOT EXISTS gridbot;

-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS gridbot.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    api_key_hash VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de configuraciones de trading
CREATE TABLE IF NOT EXISTS gridbot.trading_configs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES gridbot.users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL DEFAULT 'grid',
    symbol VARCHAR(20) NOT NULL,
    min_price DECIMAL(20, 8) NOT NULL,
    max_price DECIMAL(20, 8) NOT NULL,
    grid_levels INTEGER NOT NULL DEFAULT 10,
    quantity_per_trade DECIMAL(20, 8) NOT NULL,
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de balances
CREATE TABLE IF NOT EXISTS gridbot.balances (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES gridbot.users(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    free_balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    locked_balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_balance DECIMAL(20, 8) GENERATED ALWAYS AS (free_balance + locked_balance) STORED,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, symbol)
);

-- Tabla de órdenes
CREATE TABLE IF NOT EXISTS gridbot.orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES gridbot.users(id) ON DELETE CASCADE,
    config_id INTEGER REFERENCES gridbot.trading_configs(id) ON DELETE CASCADE,
    binance_order_id BIGINT UNIQUE,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(20) NOT NULL DEFAULT 'LIMIT',
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    executed_qty DECIMAL(20, 8) DEFAULT 0,
    cummulative_quote_qty DECIMAL(20, 8) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de trades ejecutados
CREATE TABLE IF NOT EXISTS gridbot.trades (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES gridbot.users(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES gridbot.orders(id) ON DELETE CASCADE,
    binance_trade_id BIGINT UNIQUE,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    quote_qty DECIMAL(20, 8) NOT NULL,
    commission DECIMAL(20, 8) DEFAULT 0,
    commission_asset VARCHAR(20),
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de métricas de rendimiento
CREATE TABLE IF NOT EXISTS gridbot.performance_metrics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES gridbot.users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_volume DECIMAL(20, 8) NOT NULL DEFAULT 0,
    trade_count INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL(5, 4) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 6) DEFAULT 0,
    max_drawdown DECIMAL(10, 6) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, date)
);

-- Tabla de alertas
CREATE TABLE IF NOT EXISTS gridbot.alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES gridbot.users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de logs del sistema
CREATE TABLE IF NOT EXISTS gridbot.system_logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(10) NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    module VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    extra_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON gridbot.orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON gridbot.orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON gridbot.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON gridbot.orders(created_at);

CREATE INDEX IF NOT EXISTS idx_trades_user_id ON gridbot.trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON gridbot.trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON gridbot.trades(executed_at);

CREATE INDEX IF NOT EXISTS idx_balances_user_id ON gridbot.balances(user_id);
CREATE INDEX IF NOT EXISTS idx_balances_symbol ON gridbot.balances(symbol);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_user_id ON gridbot.performance_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_date ON gridbot.performance_metrics(date);

CREATE INDEX IF NOT EXISTS idx_alerts_user_id ON gridbot.alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON gridbot.alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON gridbot.alerts(created_at);

CREATE INDEX IF NOT EXISTS idx_system_logs_level ON gridbot.system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_module ON gridbot.system_logs(module);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON gridbot.system_logs(created_at);

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION gridbot.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para actualizar updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON gridbot.users
    FOR EACH ROW EXECUTE FUNCTION gridbot.update_updated_at_column();

CREATE TRIGGER update_trading_configs_updated_at BEFORE UPDATE ON gridbot.trading_configs
    FOR EACH ROW EXECUTE FUNCTION gridbot.update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON gridbot.orders
    FOR EACH ROW EXECUTE FUNCTION gridbot.update_updated_at_column();

-- Insertar usuario de prueba (solo para desarrollo)
INSERT INTO gridbot.users (email, username, password_hash, is_verified)
VALUES ('admin@gridbot.com', 'admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/HS.i8mG', true)
ON CONFLICT (email) DO NOTHING;

-- Comentarios para documentación
COMMENT ON SCHEMA gridbot IS 'Esquema principal para la aplicación GridBot';
COMMENT ON TABLE gridbot.users IS 'Tabla de usuarios del sistema';
COMMENT ON TABLE gridbot.trading_configs IS 'Configuraciones de estrategias de trading';
COMMENT ON TABLE gridbot.balances IS 'Balances de activos por usuario';
COMMENT ON TABLE gridbot.orders IS 'Órdenes de trading';
COMMENT ON TABLE gridbot.trades IS 'Trades ejecutados';
COMMENT ON TABLE gridbot.performance_metrics IS 'Métricas de rendimiento diarias';
COMMENT ON TABLE gridbot.alerts IS 'Alertas del sistema';
COMMENT ON TABLE gridbot.system_logs IS 'Logs del sistema';
