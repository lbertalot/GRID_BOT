#!/bin/bash
# Script de configuración para despliegue en Heroku
# Este script ayuda a configurar el pipeline de Heroku para GridBot

set -e

echo "🚀 Configurando GridBot para despliegue en Heroku"
echo "=================================================="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "Procfile" ]; then
    echo "❌ Error: Procfile no encontrado. Ejecuta este script desde la raíz del proyecto."
    exit 1
fi

# Verificar que Heroku CLI está instalado
if ! command -v heroku &> /dev/null; then
    echo "❌ Error: Heroku CLI no está instalado."
    echo "   Instálalo desde: https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Verificar login
echo "📋 Verificando autenticación en Heroku..."
if ! heroku auth:whoami &> /dev/null; then
    echo "⚠️  No estás autenticado en Heroku."
    echo "   Ejecuta: heroku login"
    exit 1
fi

echo "✅ Autenticado como: $(heroku auth:whoami)"
echo ""

# Obtener información del pipeline
PIPELINE_ID="afd9fd09-5489-42a8-b256-8611d5cee54a"
echo "📦 Pipeline ID: $PIPELINE_ID"
echo ""

# Listar apps en el pipeline
echo "📱 Apps en el pipeline:"
heroku pipelines:apps $PIPELINE_ID || echo "⚠️  No se pudieron obtener las apps del pipeline"
echo ""

echo "✅ Script de verificación completado"
echo ""
echo "Siguientes pasos:"
echo "1. Configurar variables de entorno (ver DEPLOY_HEROKU.md)"
echo "2. Añadir addons si no existen"
echo "3. Desplegar código: git push heroku main"
