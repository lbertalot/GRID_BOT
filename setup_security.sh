#!/bin/bash

# Script para configurar permisos de seguridad en GridBot
echo "🔒 Configurando permisos de seguridad para GridBot..."

# Verificar si existe el archivo .env
if [ -f ".env" ]; then
    echo "📁 Configurando permisos para .env..."
    # Establecer permisos solo para el propietario (600)
    chmod 600 .env
    echo "✅ Permisos de .env configurados (600)"
else
    echo "⚠️  Archivo .env no encontrado. Asegúrate de crearlo con las variables necesarias."
fi

# Verificar si existe el directorio de logs
if [ ! -d "logs" ]; then
    mkdir logs
    echo "📁 Directorio de logs creado"
fi

# Configurar permisos para logs
chmod 755 logs
echo "✅ Permisos de logs configurados (755)"

# Verificar archivos de configuración
echo "🔍 Verificando archivos de configuración..."

# Verificar que las variables críticas estén en .env
if [ -f ".env" ]; then
    echo "📋 Variables requeridas en .env:"
    echo "   - BINANCE_API_KEY"
    echo "   - BINANCE_API_SECRET"
    echo "   - API_KEY (para autenticación)"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - TELEGRAM_CHAT_ID"
    echo ""
    echo "💡 Asegúrate de que todas estas variables estén configuradas."
fi

echo ""
echo "🚀 Configuración de seguridad completada!"
echo "📝 Recuerda:"
echo "   - Nunca commits el archivo .env"
echo "   - Usa API keys seguras y únicas"
echo "   - Revisa los logs regularmente"
echo "   - Monitorea las alertas de Telegram" 