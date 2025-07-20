#!/usr/bin/env python3
"""
Script final para verificar y corregir la base de datos
"""

import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine, text

def final_database_check():
    """Verificación final de la base de datos"""
    
    load_dotenv()
    
    print("🔍 Verificación final de la base de datos...")
    
    # 1. Verificar configuración actual
    print("\n📋 Configuración actual:")
    print(f"   DATABASE_URL: {os.getenv('DATABASE_URL')}")
    
    # 2. Crear URL síncrona correcta
    sync_url = "postgresql://griduser:gridpass@db:5432/gridbot"
    print(f"   URL síncrona: {sync_url}")
    
    # 3. Probar conexión directa
    print("\n🔌 Probando conexión directa...")
    try:
        conn = psycopg2.connect(
            host="db",
            port="5432",
            database="gridbot",
            user="griduser",
            password="gridpass"
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"   ✅ PostgreSQL conectado: {version[0]}")
        
        # Verificar tablas
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        print(f"   📊 Tablas encontradas: {len(tables)}")
        for table in tables:
            print(f"      - {table[0]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Error en conexión directa: {e}")
        return False
    
    # 4. Probar SQLAlchemy
    print("\n🔌 Probando SQLAlchemy...")
    try:
        engine = create_engine(sync_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version = result.fetchone()
            print(f"   ✅ SQLAlchemy conectado: {version[0]}")
            
            # Probar consulta a trades
            result = connection.execute(text("SELECT COUNT(*) FROM trades;"))
            count = result.fetchone()[0]
            print(f"   📈 Registros en trades: {count}")
        
        engine.dispose()
        
    except Exception as e:
        print(f"   ❌ Error en SQLAlchemy: {e}")
        return False
    
    # 5. Insertar registro de prueba
    print("\n🧪 Insertando registro de prueba...")
    try:
        engine = create_engine(sync_url)
        with engine.connect() as connection:
            connection.execute(text("""
                INSERT INTO trades (symbol, side, quantity, entry_price, timestamp)
                VALUES ('TEST', 'BUY', 0.001, 100.0, CURRENT_TIMESTAMP)
                ON CONFLICT DO NOTHING;
            """))
            connection.commit()
            print("   ✅ Registro de prueba insertado")
        
        engine.dispose()
        
    except Exception as e:
        print(f"   ❌ Error insertando registro: {e}")
        return False
    
    print("\n🎉 ¡Base de datos completamente funcional!")
    return True

if __name__ == "__main__":
    final_database_check() 