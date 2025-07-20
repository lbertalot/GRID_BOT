#!/usr/bin/env python3
"""
Script para inicializar la base de datos
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def init_database():
    """Inicializa la base de datos y crea las tablas"""
    
    load_dotenv()
    
    print("🔧 Inicializando base de datos...")
    
    # Configurar URL síncrona
    sync_url = os.getenv('DATABASE_URL', '').replace('+asyncpg', '')
    if not sync_url:
        sync_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    
    print(f"🔗 Conectando a: {sync_url}")
    
    try:
        # Crear engine
        engine = create_engine(sync_url)
        
        # Crear tablas
        print("📋 Creando tablas...")
        
        # Tabla trades
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    quantity DECIMAL(20, 8) NOT NULL,
                    entry_price DECIMAL(20, 8) NOT NULL,
                    exit_price DECIMAL(20, 8),
                    profit_loss DECIMAL(20, 8),
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Crear índices
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
                CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
            """))
            
            connection.commit()
            print("   ✅ Tabla 'trades' creada")
        
        # Verificar tablas creadas
        print("\n📊 Verificando tablas creadas...")
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = result.fetchall()
            
            for table in tables:
                print(f"   📋 - {table[0]}")
        
        engine.dispose()
        print("\n🎉 Base de datos inicializada correctamente!")
        
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")

if __name__ == "__main__":
    init_database() 