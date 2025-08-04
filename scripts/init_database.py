#!/usr/bin/env python3
"""
Script para inicializar la base de datos
Crea todas las tablas necesarias para el Grid Trading Bot
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.models.base import Base
from app.models.trade import Trade
from app.models.grid_config import GridConfig
from app.models.asset_limit import AssetLimit

def init_database():
    """Inicializa la base de datos con todas las tablas"""
    
    # URL de la base de datos
    database_url = os.getenv('DATABASE_URL', 'postgresql://griduser:gridpass@db:5432/gridbot')
    
    print(f"🔧 Inicializando base de datos...")
    print(f"📊 URL: {database_url}")
    
    try:
        # Crear engine
        engine = create_engine(database_url)
        
        # Verificar conexión
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ Conectado a PostgreSQL: {version}")
        
        # Crear todas las tablas
        print("📋 Creando tablas...")
        Base.metadata.create_all(engine)
        
        # Verificar tablas creadas
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]
            
            print(f"✅ Tablas creadas: {', '.join(tables)}")
            
            # Verificar tablas específicas
            expected_tables = ['trades', 'grid_configs', 'asset_limits']
            missing_tables = [table for table in expected_tables if table not in tables]
            
            if missing_tables:
                print(f"⚠️  Tablas faltantes: {', '.join(missing_tables)}")
            else:
                print("✅ Todas las tablas esperadas fueron creadas")
        
        print("🎉 Base de datos inicializada exitosamente!")
        return True
        
    except OperationalError as e:
        print(f"❌ Error de conexión: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def verify_database():
    """Verifica que la base de datos esté funcionando correctamente"""
    
    database_url = os.getenv('DATABASE_URL', 'postgresql://griduser:gridpass@db:5432/gridbot')
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Verificar tablas
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]
            
            print(f"📊 Tablas disponibles: {', '.join(tables)}")
            
            # Verificar estructura de tabla trades
            if 'trades' in tables:
                result = conn.execute(text("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'trades'
                    ORDER BY ordinal_position;
                """))
                columns = [(row[0], row[1]) for row in result.fetchall()]
                print(f"📋 Estructura de tabla 'trades':")
                for col_name, col_type in columns:
                    print(f"   • {col_name}: {col_type}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error verificando base de datos: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Inicializando base de datos del Grid Trading Bot")
    print("=" * 50)
    
    # Inicializar base de datos
    if init_database():
        print("\n" + "=" * 50)
        print("🔍 Verificando base de datos...")
        verify_database()
    else:
        print("❌ Falló la inicialización de la base de datos")
        sys.exit(1) 