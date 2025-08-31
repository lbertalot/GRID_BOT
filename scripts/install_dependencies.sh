#!/bin/bash

# Script de instalación de dependencias para Grid Trading Bot
# Permite elegir entre diferentes configuraciones de requirements

set -e

echo "🚀 Instalación de Dependencias - Grid Trading Bot"
echo "=================================================="

# Verificar si estamos en un entorno virtual
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Advertencia: No se detectó un entorno virtual activo"
    echo "   Se recomienda usar un entorno virtual para este proyecto"
    read -p "¿Desea continuar de todas formas? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Instalación cancelada"
        exit 1
    fi
fi

# Instalación unificada
echo ""
echo "📦 Instalando dependencias unificadas..."
echo "   (Incluye python-binance + unicorn-binance-websocket-api + ML)"
echo ""

echo "📥 Instalando todas las dependencias..."
pip install -r requirements.txt
echo "✅ Instalación unificada completada"

echo ""
echo "🔍 Verificando instalación..."
python3 -c "
import sys
packages = ['fastapi', 'uvicorn', 'sqlalchemy', 'asyncpg', 'pydantic']
missing = []

for package in packages:
    try:
        __import__(package)
        print(f'✅ {package}')
    except ImportError:
        missing.append(package)
        print(f'❌ {package}')

if missing:
    print(f'\\n⚠️  Paquetes faltantes: {missing}')
    sys.exit(1)
else:
    print('\\n🎉 Todas las dependencias principales están instaladas correctamente')
"

echo ""
echo "📋 Próximos pasos:"
echo "1. Configurar variables de entorno (.env)"
echo "2. Ejecutar migraciones de base de datos"
echo "3. Iniciar el servidor: python -m uvicorn app.main:app --reload"
echo ""
echo "📚 Documentación: MEJORAS_REQUIREMENTS.md" 