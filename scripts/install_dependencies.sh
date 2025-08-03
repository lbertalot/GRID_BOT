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

# Mostrar opciones
echo ""
echo "📦 Opciones de instalación:"
echo "1) Instalación estándar (python-binance)"
echo "2) Instalación con WebSocket avanzado (unicorn-binance-websocket-api)"
echo "3) Instalación completa (ambas librerías)"
echo ""

read -p "Seleccione una opción (1-3): " choice

case $choice in
    1)
        echo "📥 Instalando dependencias estándar..."
        pip install -r requirements.txt
        echo "✅ Instalación estándar completada"
        ;;
    2)
        echo "📥 Instalando dependencias con WebSocket avanzado..."
        pip install -r requirements_websocket.txt
        echo "✅ Instalación con WebSocket avanzado completada"
        ;;
    3)
        echo "📥 Instalando dependencias completas..."
        pip install -r requirements.txt
        pip install unicorn-binance-websocket-api==1.45.0
        echo "✅ Instalación completa finalizada"
        ;;
    *)
        echo "❌ Opción inválida"
        exit 1
        ;;
esac

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