#!/usr/bin/env python3
"""
Script de release para Heroku que ejecuta migraciones de base de datos.
Se ejecuta automáticamente después del build y antes de iniciar los dynos.
"""
import subprocess
import sys
import os


def run_command(cmd, description):
    """Ejecuta un comando y maneja errores"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ {description} completado")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en {description}:")
        print(e.stderr)
        return False


def main():
    """Función principal del script de release"""
    print("=" * 60)
    print("🚀 Ejecutando release phase para GridBot")
    print("=" * 60)
    
    # Paso 1: Arreglar tabla alembic_version si es necesario
    if not run_command(
        "python scripts/fix_alembic_table.py",
        "Arreglando tabla alembic_version"
    ):
        print("⚠️  Advertencia: No se pudo arreglar alembic_version, continuando...")
    
    # Paso 2: Ejecutar migraciones
    if not run_command(
        "alembic upgrade head",
        "Ejecutando migraciones de Alembic"
    ):
        print("❌ Error ejecutando migraciones")
        sys.exit(1)
    
    # Paso 3: Crear tablas faltantes usando Base.metadata si es necesario
    # Esto asegura que todas las tablas definidas en modelos existan
    print("🔄 Verificando y creando tablas faltantes desde modelos SQLAlchemy...")
    try:
        import sys
        import os
        sys.path.insert(0, os.getcwd())
        
        from sqlalchemy import create_engine, inspect
        from app.models.base import Base
        # Importar todos los modelos para que se registren en Base.metadata
        from app.models import trade, alerts, performance_metrics, system_config
        from app.models import grid_config, asset_limit, balance, system_setting
        
        database_url = os.getenv("DATABASE_URL", "")
        if database_url:
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            engine = create_engine(database_url)
            inspector = inspect(engine)
            existing_tables = set(inspector.get_table_names())
            
            # Crear solo las tablas que no existen
            metadata_tables = set(Base.metadata.tables.keys())
            missing_tables = metadata_tables - existing_tables
            
            if missing_tables:
                print(f"📝 Creando tablas faltantes: {', '.join(missing_tables)}")
                # Crear solo las tablas faltantes
                for table_name in missing_tables:
                    table = Base.metadata.tables[table_name]
                    table.create(engine, checkfirst=True)
                print(f"✅ {len(missing_tables)} tablas creadas exitosamente")
            else:
                print("✅ Todas las tablas necesarias ya existen")
    except Exception as e:
        print(f"⚠️  Advertencia al crear tablas desde modelos: {e}")
        print("   Las migraciones deberían haber creado todas las tablas necesarias")
    
    print("=" * 60)
    print("✅ Release phase completado exitosamente")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
