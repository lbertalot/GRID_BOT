#!/usr/bin/env python3
"""
Script para configurar automáticamente el archivo .env
Genera un archivo .env optimizado para desarrollo local
"""

import os
import secrets
from pathlib import Path

def generate_secret_key():
    """Genera una clave secreta segura"""
    return secrets.token_urlsafe(32)

def create_env_file():
    """Crea el archivo .env con configuraciones optimizadas"""
    
    # Obtener la ruta del proyecto
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    # Verificar si ya existe
    if env_file.exists():
        print(f"⚠️  El archivo {env_file} ya existe")
        response = input("¿Desea sobrescribirlo? (y/N): ")
        if response.lower() != 'y':
            print("❌ Operación cancelada")
            return False
    
    # Configuración del archivo .env
    env_content = f"""# =============================================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# =============================================================================
DATABASE_URL=postgresql://griduser:gridpass@localhost:5432/gridbot
POSTGRES_USER=griduser
POSTGRES_PASSWORD=gridpass
POSTGRES_DB=gridbot
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# =============================================================================
# CONFIGURACIÓN DE REDIS Y CELERY
# =============================================================================
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# =============================================================================
# CONFIGURACIÓN DE BINANCE (TESTNET PARA DESARROLLO)
# =============================================================================
# IMPORTANTE: Usar testnet para desarrollo, cambiar a false para producción
BINANCE_API_KEY=sGe6sH9j9iwFQM8liSvA29zQVThsMQEDwLp3xn8WIEbnJg9n7DRWLmgpN8gTcMHC
BINANCE_SECRET_KEY=GCFZII1X4DfOdVJAV6bKuYg3kpvX9FguIim4uUnGgwX106Hu2kvDLIw2u016g4Ep
BINANCE_TESTNET=true
BINANCE_API_URL=https://testnet.binance.vision/api

# =============================================================================
# CONFIGURACIÓN DE TELEGRAM
# =============================================================================
TELEGRAM_BOT_TOKEN=8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8
TELEGRAM_CHAT_ID=1248403886

# =============================================================================
# CONFIGURACIÓN DE SEGURIDAD
# =============================================================================
SECRET_KEY={generate_secret_key()}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# =============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# =============================================================================
DEBUG=true
ENVIRONMENT=development
DOCKER_ENV=false
LOG_LEVEL=INFO
API_V1_STR=/api/v1
PROJECT_NAME=GridBot Trading Platform
BACKEND_CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:8000"]

# =============================================================================
# CONFIGURACIÓN DE MONITOREO
# =============================================================================
PROMETHEUS_MULTIPROC_DIR=/tmp
ENABLE_METRICS=true
ENABLE_HEALTH_CHECKS=true

# =============================================================================
# CONFIGURACIÓN DE TRADING
# =============================================================================
DEFAULT_GRID_LEVELS=10
MIN_NOTIONAL=10.0
MAX_ACTIVE_ORDERS=100
TRADING_ENABLED=true
PAPER_TRADING=true

# =============================================================================
# CONFIGURACIÓN DE RIESGO
# =============================================================================
MAX_DAILY_LOSS_PERCENT=5.0
MAX_POSITION_SIZE_PERCENT=20.0
STOP_LOSS_PERCENT=10.0
MAX_DRAWDOWN_PERCENT=15.0

# =============================================================================
# CONFIGURACIÓN DE REBALANCEO
# =============================================================================
AUTO_REBALANCE_ENABLED=true
REBALANCE_FREQUENCY=3600
MIN_BALANCE_THRESHOLD=10.0

# =============================================================================
# CONFIGURACIÓN DE MACHINE LEARNING
# =============================================================================
ML_ENABLED=false
MODEL_UPDATE_FREQUENCY=86400
PREDICTION_CONFIDENCE_THRESHOLD=0.7

# =============================================================================
# CONFIGURACIÓN DE BACKTESTING
# =============================================================================
BACKTEST_DATA_DAYS=30
BACKTEST_ENABLED=true

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
# CONFIGURACIÓN DE WEBSOCKET (NUEVAS MEJORAS)
# =============================================================================
WEBSOCKET_ADVANCED=false
BINANCE_WEBSOCKET_CHANNELS=kline_1m,ticker,bookTicker
BINANCE_WEBSOCKET_SYMBOLS=BTCUSDT,ETHUSDT
ENABLE_WEBSOCKET_METRICS=true
WEBSOCKET_RECONNECT_DELAY=5

# =============================================================================
# CONFIGURACIÓN DE CORREO ELECTRÓNICO (OPCIONAL)
# =============================================================================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=noreply@gridbot.com

# =============================================================================
# CONFIGURACIÓN DE SLACK (OPCIONAL)
# =============================================================================
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
SLACK_CHANNEL=#gridbot-alerts

# =============================================================================
# CONFIGURACIÓN DE AWS S3 (OPCIONAL)
# =============================================================================
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=gridbot-data

# =============================================================================
# CONFIGURACIÓN DE SENTRY (OPCIONAL)
# =============================================================================
SENTRY_DSN=your_sentry_dsn_here
SENTRY_ENVIRONMENT=development
"""
    
    try:
        # Crear el archivo .env
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print(f"✅ Archivo .env creado exitosamente en: {env_file}")
        print("\n📋 Configuraciones importantes:")
        print("   • Base de datos: PostgreSQL local")
        print("   • Redis: Local para cache y Celery")
        print("   • Binance: Testnet habilitado (seguro para desarrollo)")
        print("   • Paper Trading: Habilitado")
        print("   • WebSocket: Deshabilitado por defecto")
        print("\n⚠️  IMPORTANTE:")
        print("   • Cambiar BINANCE_TESTNET=false para producción")
        print("   • Configurar credenciales reales de Binance")
        print("   • Revisar configuración de Telegram")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creando archivo .env: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 Configurando Variables de Entorno - Grid Trading Bot")
    print("=" * 60)
    
    success = create_env_file()
    
    if success:
        print("\n🎉 Configuración completada exitosamente!")
        print("\n📋 Próximos pasos:")
        print("1. Revisar y ajustar configuraciones en .env")
        print("2. Ejecutar migraciones de base de datos")
        print("3. Iniciar servicios (PostgreSQL, Redis)")
        print("4. Ejecutar el servidor: python -m uvicorn app.main:app --reload")
    else:
        print("\n❌ Error en la configuración")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 