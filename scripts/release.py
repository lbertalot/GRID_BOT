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
    
    print("=" * 60)
    print("✅ Release phase completado exitosamente")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
