#!/usr/bin/env python3
"""
Script para actualizar el archivo .env existente con nuevas configuraciones
Agrega las configuraciones de WebSocket y otras mejoras
"""

import os
import re
from pathlib import Path

def update_env_file():
    """Actualiza el archivo .env existente con nuevas configuraciones"""
    
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print("❌ No se encontró el archivo .env")
        return False
    
    # Leer el archivo actual
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Configuraciones nuevas a agregar
    new_configs = """
# =============================================================================
# CONFIGURACIÓN DE WEBSOCKET (NUEVAS MEJORAS)
# =============================================================================
WEBSOCKET_ADVANCED=false
BINANCE_WEBSOCKET_CHANNELS=kline_1m,ticker,bookTicker
BINANCE_WEBSOCKET_SYMBOLS=BTCUSDT,ETHUSDT
ENABLE_WEBSOCKET_METRICS=true
WEBSOCKET_RECONNECT_DELAY=5

# =============================================================================
# CONFIGURACIÓN DE MONITOREO MEJORADO
# =============================================================================
PROMETHEUS_MULTIPROC_DIR=/tmp
ENABLE_METRICS=true
ENABLE_HEALTH_CHECKS=true

# =============================================================================
# CONFIGURACIÓN DE CACHE
# =============================================================================
CACHE_TTL=300
CACHE_MAX_SIZE=1000

# =============================================================================
# CONFIGURACIÓN DE RATE LIMITING
# =============================================================================
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# =============================================================================
# CONFIGURACIÓN DE BACKTESTING
# =============================================================================
BACKTEST_DATA_DAYS=30
BACKTEST_ENABLED=true

# =============================================================================
# CONFIGURACIÓN DE MACHINE LEARNING
# =============================================================================
ML_ENABLED=false
MODEL_UPDATE_FREQUENCY=86400
PREDICTION_CONFIDENCE_THRESHOLD=0.7

# =============================================================================
# CONFIGURACIÓN DE REBALANCEO
# =============================================================================
AUTO_REBALANCE_ENABLED=true
REBALANCE_FREQUENCY=3600
MIN_BALANCE_THRESHOLD=10.0

# =============================================================================
# CONFIGURACIÓN DE RIESGO
# =============================================================================
MAX_DAILY_LOSS_PERCENT=5.0
MAX_POSITION_SIZE_PERCENT=20.0
STOP_LOSS_PERCENT=10.0
MAX_DRAWDOWN_PERCENT=15.0

# =============================================================================
# CONFIGURACIÓN DE TRADING
# =============================================================================
DEFAULT_GRID_LEVELS=10
MIN_NOTIONAL=10.0
MAX_ACTIVE_ORDERS=100
TRADING_ENABLED=true
PAPER_TRADING=true

# =============================================================================
# CONFIGURACIÓN DE ALERTAS
# =============================================================================
ALERT_EMAIL_ENABLED=false
ALERT_SMS_ENABLED=false
ALERT_TELEGRAM_ENABLED=true

# =============================================================================
# CONFIGURACIÓN DE LOGS
# =============================================================================
LOG_FILE_PATH=./logs/gridbot.log
LOG_MAX_SIZE=1024MB
LOG_BACKUP_COUNT=5
"""
    
    # Verificar si las configuraciones ya existen
    if "WEBSOCKET_ADVANCED" in content:
        print("⚠️  Las configuraciones de WebSocket ya existen en el archivo .env")
        response = input("¿Desea actualizar de todas formas? (y/N): ")
        if response.lower() != 'y':
            print("❌ Actualización cancelada")
            return False
    
    # Agregar las nuevas configuraciones al final del archivo
    updated_content = content + new_configs
    
    # Crear backup del archivo original
    backup_file = env_file.with_suffix('.env.backup')
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Escribir el archivo actualizado
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"✅ Archivo .env actualizado exitosamente")
    print(f"📄 Backup guardado en: {backup_file}")
    
    return True

def verify_env_config():
    """Verifica que las configuraciones importantes estén presentes"""
    
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print("❌ No se encontró el archivo .env")
        return False
    
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Configuraciones críticas a verificar
    critical_configs = [
        'DATABASE_URL',
        'REDIS_URL',
        'BINANCE_API_KEY',
        'BINANCE_SECRET_KEY',
        'TELEGRAM_BOT_TOKEN',
        'SECRET_KEY'
    ]
    
    missing_configs = []
    for config in critical_configs:
        if config not in content:
            missing_configs.append(config)
    
    if missing_configs:
        print(f"⚠️  Configuraciones faltantes: {', '.join(missing_configs)}")
        return False
    
    print("✅ Todas las configuraciones críticas están presentes")
    return True

def main():
    """Función principal"""
    print("🔄 Actualizando Variables de Entorno - Grid Trading Bot")
    print("=" * 60)
    
    # Verificar configuraciones existentes
    print("🔍 Verificando configuraciones existentes...")
    if not verify_env_config():
        print("❌ Configuraciones críticas faltantes")
        return 1
    
    # Actualizar archivo
    print("\n📝 Actualizando archivo .env...")
    if update_env_file():
        print("\n🎉 Actualización completada exitosamente!")
        print("\n📋 Nuevas configuraciones agregadas:")
        print("   • WebSocket avanzado (deshabilitado por defecto)")
        print("   • Monitoreo mejorado con Prometheus")
        print("   • Configuración de cache y rate limiting")
        print("   • Configuraciones de trading y riesgo")
        print("   • Configuraciones de ML y backtesting")
        print("\n📋 Próximos pasos:")
        print("1. Revisar configuraciones en .env")
        print("2. Ejecutar migraciones de base de datos")
        print("3. Iniciar servicios (PostgreSQL, Redis)")
        print("4. Ejecutar testing de compatibilidad")
    else:
        print("\n❌ Error en la actualización")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 