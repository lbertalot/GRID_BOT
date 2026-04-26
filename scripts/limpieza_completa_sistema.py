#!/usr/bin/env python3
"""
Script de limpieza completa del sistema
Elimina archivos innecesarios y mantiene solo lo esencial
"""

import os
import shutil
import json


def limpiar_sistema():
    """Limpia completamente el sistema"""

    print("🧹 INICIANDO LIMPIEZA COMPLETA DEL SISTEMA")
    print("=" * 50)

    # Archivos y directorios a ELIMINAR
    archivos_a_eliminar = [
        # Scripts de emergencia temporales
        "scripts/cierre_emergencia_final.py",
        "scripts/cierre_manual_emergencia.py",
        "scripts/verificar_emergencia_total.py",
        "scripts/cerrar_posiciones_corregido.py",
        "scripts/cerrar_posiciones_seguro.py",
        "scripts/verificar_saldos_simple.py",
        "scripts/cerrar_posiciones_emergencia.py",
        "scripts/analisis_perdidas_estrategia.py",
        "scripts/validate_cursor_rules_realistic.py",
        "scripts/validate_cursor_rules.py",
        "scripts/cleanup_unnecessary_files.py",
        # Configuraciones de emergencia
        "grid_config_emergency_total.json",
        "grid_config_emergency_stop.json",
        "grid_config_emergency_backup_20250824_180851.json",
        "grid_config_backup_20250824_160459.json",
        "grid_config_optimized_391usdt.json",
        "grid_config_consolidated.json",
        "grid_config_optimized_market.json",
        # Archivos temporales
        "current_market_data.json",
        "compatibility_report.txt",
        # Logs antiguos
        "logs/dockers.log.backup.20250805_064442",
    ]

    # Directorios a LIMPIAR (mantener estructura pero eliminar contenido innecesario)
    directorios_a_limpiar = [
        "cache/",
        "static/",
    ]

    # Archivos a MANTENER (lista blanca)
    archivos_esenciales = [
        # Configuración principal
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.tls.yml",
        "docker-compose.websocket.yml",
        "Dockerfile",
        "requirements.txt",
        "requirements_websocket.txt",
        "pytest.ini",
        ".env",
        "env.example",
        "alembic.ini",
        # Configuración actual
        "grid_config_optimized.json",
        # Documentación esencial
        "README.md",
        "README_FINAL.md",
        "PRD.md",
        "RFC.md",
        # Estructura de directorios
        "app/",
        "docker/",
        "alembic/",
        "tests/",
        "logs/",
        "data/",
        "scripts/",
        "Docs/",
    ]

    # Eliminar archivos innecesarios
    print("🗑️ Eliminando archivos innecesarios...")
    for archivo in archivos_a_eliminar:
        if os.path.exists(archivo):
            try:
                os.remove(archivo)
                print(f"   ✅ Eliminado: {archivo}")
            except Exception as e:
                print(f"   ❌ Error eliminando {archivo}: {e}")

    # Limpiar directorios
    print("\n🧹 Limpiando directorios...")
    for directorio in directorios_a_limpiar:
        if os.path.exists(directorio):
            try:
                # Eliminar contenido pero mantener directorio
                for item in os.listdir(directorio):
                    item_path = os.path.join(directorio, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                print(f"   ✅ Limpiado: {directorio}")
            except Exception as e:
                print(f"   ❌ Error limpiando {directorio}: {e}")

    # Limpiar scripts innecesarios
    print("\n📁 Limpiando scripts innecesarios...")
    scripts_dir = "scripts/"
    if os.path.exists(scripts_dir):
        for archivo in os.listdir(scripts_dir):
            if archivo.endswith(".py") and archivo not in [
                "limpieza_completa_sistema.py",  # Este script
                "get_current_prices_and_balances.py",
                "optimize_config_with_current_data.py",
            ]:
                try:
                    os.remove(os.path.join(scripts_dir, archivo))
                    print(f"   ✅ Eliminado script: {archivo}")
                except Exception as e:
                    print(f"   ❌ Error eliminando script {archivo}: {e}")

    # Verificar estructura esencial
    print("\n🔍 Verificando estructura esencial...")
    for item in archivos_esenciales:
        if os.path.exists(item):
            print(f"   ✅ Mantenido: {item}")
        else:
            print(f"   ⚠️ No encontrado: {item}")

    print("\n✅ LIMPIEZA COMPLETADA")
    print("=" * 50)


def crear_configuracion_minima():
    """Crea una configuración mínima y segura"""

    print("\n⚙️ Creando configuración mínima...")

    # Configuración mínima de trading
    config_minima = {
        "_config_metadata": {
            "created_at": "2025-09-01T16:30:00Z",
            "version": "2.5_minimal",
            "status": "STOPPED",
            "reason": "Sistema en revisión - Trading detenido",
        },
        "BTCUSDT": {
            "symbol": "BTCUSDT",
            "is_active": False,
            "min_price": 108000,
            "max_price": 109000,
            "grids": 0,
            "quantity": 0,
            "investment_amount": 0,
        },
        "ETHUSDT": {
            "symbol": "ETHUSDT",
            "is_active": False,
            "min_price": 4400,
            "max_price": 4410,
            "grids": 0,
            "quantity": 0,
            "investment_amount": 0,
        },
    }

    # Guardar configuración mínima
    with open("grid_config_minimal.json", "w") as f:
        json.dump(config_minima, f, indent=2)

    print("   ✅ Configuración mínima creada: grid_config_minimal.json")


def generar_reporte_limpieza():
    """Genera reporte de la limpieza"""

    print("\n📊 REPORTE DE LIMPIEZA")
    print("=" * 30)

    # Contar archivos por directorio
    directorios_principales = ["app", "docker", "tests", "scripts", "Docs"]

    for directorio in directorios_principales:
        if os.path.exists(directorio):
            archivos = len(
                [
                    f
                    for f in os.listdir(directorio)
                    if os.path.isfile(os.path.join(directorio, f))
                ]
            )
            print(f"   📁 {directorio}/: {archivos} archivos")

    # Verificar archivos críticos
    archivos_criticos = [
        "docker-compose.yml",
        "requirements.txt",
        "app/main.py",
        "app/core/config.py",
        "grid_config_optimized.json",
    ]

    print("\n🔑 Archivos críticos:")
    for archivo in archivos_criticos:
        if os.path.exists(archivo):
            print(f"   ✅ {archivo}")
        else:
            print(f"   ❌ {archivo} - FALTANTE")


if __name__ == "__main__":
    try:
        limpiar_sistema()
        crear_configuracion_minima()
        generar_reporte_limpieza()
        print("\n🎯 SISTEMA LIMPIO Y LISTO PARA REVISIÓN")
    except Exception as e:
        print(f"❌ Error en limpieza: {e}")
