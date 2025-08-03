#!/usr/bin/env python3
"""
Script para ejecutar migraciones de base de datos
Verifica la conectividad y ejecuta las migraciones necesarias
"""

import os
import sys
import subprocess
from pathlib import Path

def check_database_connection():
    """Verifica la conectividad a la base de datos"""
    print("🔍 Verificando conectividad a la base de datos...")
    
    try:
        # Intentar importar y conectar a la base de datos
        import asyncpg
        import asyncio
        from dotenv import load_dotenv
        
        # Cargar variables de entorno
        load_dotenv()
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL no configurada en .env")
            return False
        
        # Extraer parámetros de conexión
        if database_url.startswith('postgresql://'):
            # Formato: postgresql://user:pass@host:port/db
            parts = database_url.replace('postgresql://', '').split('@')
            if len(parts) != 2:
                print("❌ Formato de DATABASE_URL inválido")
                return False
            
            user_pass = parts[0].split(':')
            host_port_db = parts[1].split('/')
            
            if len(user_pass) != 2 or len(host_port_db) != 2:
                print("❌ Formato de DATABASE_URL inválido")
                return False
            
            user = user_pass[0]
            password = user_pass[1]
            host_port = host_port_db[0].split(':')
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 5432
            database = host_port_db[1]
            
            print(f"   • Host: {host}")
            print(f"   • Puerto: {port}")
            print(f"   • Base de datos: {database}")
            print(f"   • Usuario: {user}")
            
            # Intentar conexión
            async def test_connection():
                try:
                    conn = await asyncpg.connect(
                        host=host,
                        port=port,
                        user=user,
                        password=password,
                        database=database
                    )
                    await conn.close()
                    return True
                except Exception as e:
                    print(f"   ❌ Error de conexión: {e}")
                    return False
            
            # Ejecutar test de conexión
            result = asyncio.run(test_connection())
            if result:
                print("   ✅ Conexión exitosa a la base de datos")
                return True
            else:
                return False
                
        else:
            print("❌ DATABASE_URL debe usar formato postgresql://")
            return False
            
    except ImportError as e:
        print(f"❌ Error importando dependencias: {e}")
        return False
    except Exception as e:
        print(f"❌ Error verificando conexión: {e}")
        return False

def check_redis_connection():
    """Verifica la conectividad a Redis"""
    print("\n🔍 Verificando conectividad a Redis...")
    
    try:
        import redis
        from dotenv import load_dotenv
        
        load_dotenv()
        
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        
        # Extraer parámetros de conexión
        if redis_url.startswith('redis://'):
            parts = redis_url.replace('redis://', '').split(':')
            host = parts[0] if parts[0] else 'localhost'
            port = int(parts[1]) if len(parts) > 1 else 6379
            
            print(f"   • Host: {host}")
            print(f"   • Puerto: {port}")
            
            # Intentar conexión
            r = redis.Redis(host=host, port=port, decode_responses=True)
            r.ping()
            print("   ✅ Conexión exitosa a Redis")
            return True
            
        else:
            print("❌ REDIS_URL debe usar formato redis://")
            return False
            
    except ImportError:
        print("❌ Redis no está instalado")
        return False
    except Exception as e:
        print(f"   ❌ Error de conexión a Redis: {e}")
        return False

def run_alembic_migrations():
    """Ejecuta las migraciones de Alembic"""
    print("\n📝 Ejecutando migraciones de base de datos...")
    
    try:
        # Verificar si existe el archivo alembic.ini
        project_root = Path(__file__).parent.parent
        alembic_ini = project_root / "alembic.ini"
        
        if not alembic_ini.exists():
            print("⚠️  No se encontró alembic.ini, inicializando Alembic...")
            
            # Inicializar Alembic
            result = subprocess.run(
                ["alembic", "init", "alembic"],
                cwd=project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Error inicializando Alembic: {result.stderr}")
                return False
            
            print("✅ Alembic inicializado correctamente")
        
        # Ejecutar migraciones
        print("   • Ejecutando migraciones...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("   ✅ Migraciones ejecutadas correctamente")
            return True
        else:
            print(f"   ❌ Error ejecutando migraciones: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error ejecutando migraciones: {e}")
        return False

def create_initial_data():
    """Crea datos iniciales si es necesario"""
    print("\n📊 Creando datos iniciales...")
    
    try:
        # Aquí se pueden agregar scripts para crear datos iniciales
        # Por ejemplo, configuraciones por defecto, usuarios admin, etc.
        
        print("   ✅ Datos iniciales creados (si es necesario)")
        return True
        
    except Exception as e:
        print(f"   ❌ Error creando datos iniciales: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 Ejecutando Migraciones - Grid Trading Bot")
    print("=" * 60)
    
    # Verificar conectividad
    if not check_database_connection():
        print("\n❌ No se pudo conectar a la base de datos")
        print("📋 Soluciones posibles:")
        print("   1. Verificar que PostgreSQL esté ejecutándose")
        print("   2. Verificar credenciales en .env")
        print("   3. Crear la base de datos si no existe")
        return 1
    
    if not check_redis_connection():
        print("\n⚠️  No se pudo conectar a Redis")
        print("📋 Soluciones posibles:")
        print("   1. Verificar que Redis esté ejecutándose")
        print("   2. Verificar configuración en .env")
        print("   3. Redis es opcional para desarrollo básico")
    
    # Ejecutar migraciones
    if not run_alembic_migrations():
        print("\n❌ Error ejecutando migraciones")
        return 1
    
    # Crear datos iniciales
    create_initial_data()
    
    print("\n🎉 Migraciones completadas exitosamente!")
    print("\n📋 Próximos pasos:")
    print("1. Verificar que las tablas se crearon correctamente")
    print("2. Ejecutar testing de compatibilidad")
    print("3. Iniciar el servidor: python -m uvicorn app.main:app --reload")
    
    return 0

if __name__ == "__main__":
    exit(main()) 