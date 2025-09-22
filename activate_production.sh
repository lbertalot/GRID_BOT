#!/bin/bash
echo "🚀 ACTIVANDO GRIDBOT V2.5 PARA PRODUCCIÓN CON DINERO REAL"
echo "=================================================="

# Configurar variables de entorno para producción
export PAPER_TRADING=false
export BINANCE_TESTNET=false
export FORCE_REAL_MODE=true
export TRADING_ENABLED=false
export EMERGENCY_STOP=true

echo "✅ Variables de entorno configuradas para producción"

# Reiniciar API con configuración de producción
echo "🔄 Reiniciando API con configuración de producción..."
docker-compose restart api

# Esperar que la API se inicie
echo "⏳ Esperando que la API se inicie..."
sleep 15

# Verificar que la API esté funcionando
echo "🔍 Verificando estado de la API..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ API funcionando correctamente"
else
    echo "❌ Error: API no disponible"
    exit 1
fi

# Verificar configuración en el contenedor
echo "🔍 Verificando configuración en el contenedor..."
docker-compose exec api env | grep -E "(PAPER_TRADING|BINANCE_TESTNET|FORCE_REAL_MODE|TRADING_ENABLED)"

# Ejecutar auditoría final
echo "🔍 Ejecutando auditoría final con datos reales..."
BINANCE_API_KEY="xxsGe6sH9j9iwFQM8liSvA29zQVThsMQEDwLp3xn8WIEbnJg9n7DRWLmgpN8gTcMHC" \
BINANCE_SECRET_KEY="xxGCFZII1X4DfOdVJAV6bKuYg3kpvX9FguIim4uUnGgwX106Hu2kvDLIw2u016g4Ep" \
BINANCE_TESTNET="false" \
python3 final_audit.py

echo "🎉 Proceso de activación completado"
