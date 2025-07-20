#!/usr/bin/env python3
"""
Script para verificar la configuración de la base de datos
"""

import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def check_database_config():
    """Verifica la configuración de la base de datos"""
    
    load_dotenv()
    
    print("🔍 Verificando configuración de base de datos...")
    
    # 1. Verificar variables de entorno
    print("\n📋 Variables de entorno:")
    print(f"   POSTGRES_USER: {os.getenv('POSTGRES_USER')}")
    print(f"   POSTGRES_PASSWORD: {os.getenv('POSTGRES_PASSWORD')}")
    print(f"   POSTGRES_DB: {os.getenv('POSTGRES_DB')}")
    print(f"   POSTGRES_HOST: {os.getenv('POSTGRES_HOST')}")
    print(f"   POSTGRES_PORT: {os.getenv('POSTGRES_PORT')}")
    print(f"   DATABASE_URL: {os.getenv('DATABASE_URL')}")
    
    # 2. Probar conexión directa con psycopg2
    print("\n🔌 Probando conexión directa con psycopg2...")
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB', 'gridbot'),
            user=os.getenv('POSTGRES_USER', 'griduser'),
            password=os.getenv('POSTGRES_PASSWORD', 'gridpass')
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"   ✅ Conexión exitosa: {version[0]}")
        
        # Verificar tablas
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cursor.fetchall()
        print(f"   📊 Tablas encontradas: {len(tables)}")
        for table in tables:
            print(f"      - {table[0]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Error en conexión directa: {e}")
    
    # 3. Probar conexión con SQLAlchemy
    print("\n🔌 Probando conexión con SQLAlchemy...")
    try:
        # Usar URL síncrona
        sync_url = os.getenv('DATABASE_URL', '').replace('+asyncpg', '')
        if not sync_url:
            sync_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
        
        print(f"   🔗 URL síncrona: {sync_url}")
        
        engine = create_engine(sync_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version = result.fetchone()
            print(f"   ✅ SQLAlchemy conectado: {version[0]}")
        
        engine.dispose()
        
    except Exception as e:
        print(f"   ❌ Error en SQLAlchemy: {e}")
    
    # 4. Verificar si las tablas existen
    print("\n📊 Verificando estructura de tablas...")
    try:
        engine = create_engine(sync_url)
        with engine.connect() as connection:
            # Verificar si existe la tabla trades
            result = connection.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'trades'
                );
            """))
            trades_exists = result.fetchone()[0]
            print(f"   📋 Tabla 'trades' existe: {trades_exists}")
            
            if trades_exists:
                # Contar registros
                result = connection.execute(text("SELECT COUNT(*) FROM trades;"))
                count = result.fetchone()[0]
                print(f"   📈 Registros en 'trades': {count}")
        
        engine.dispose()
        
    except Exception as e:
        print(f"   ❌ Error verificando tablas: {e}")

if __name__ == "__main__":
    check_database_config() 