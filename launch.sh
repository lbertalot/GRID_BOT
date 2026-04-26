#!/bin/bash

# Script para el lanzamiento controlado de GridBot v2.5 a Producción

echo "====================================================="
echo "== LANZADOR DE PRODUCCIÓN DE GRIDBOT V2.5 =="
echo "====================================================="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ ERROR: No se encontró docker-compose.yml en el directorio actual."
    echo "   Asegúrate de ejecutar este script desde el directorio raíz de GridBot."
    exit 1
fi

# Paso 1: Detener cualquier servicio en ejecución
echo "[PASO 1/4] Deteniendo todos los servicios actuales..."
docker-compose down
echo "✅ Servicios detenidos."
echo ""

# Paso 2: Verificación manual del usuario
echo "[PASO 2/4] VERIFICACIÓN MANUAL REQUERIDA:"
echo "Por favor, asegúrate de haber renombrado 'production.env' a '.env' y"
echo "de haber introducido tus API keys de producción REALES."
echo ""
echo "⚠️  ADVERTENCIA: Este script iniciará GridBot con DINERO REAL."
echo "   Asegúrate de que todas las configuraciones sean correctas."
echo ""
read -p "Presiona ENTER para continuar si has completado este paso..."

# Verificar que el archivo .env existe
if [ ! -f ".env" ]; then
    echo "❌ ERROR: No se encontró el archivo .env"
    echo "   Por favor, renombra 'production.env' a '.env' y configura tus credenciales."
    exit 1
fi

# Verificar que las credenciales no son placeholders
if grep -q "YOUR_REAL_API_KEY_HERE" .env; then
    echo "❌ ERROR: Las credenciales de Binance no han sido configuradas."
    echo "   Por favor, edita el archivo .env y reemplaza los placeholders con tus credenciales reales."
    exit 1
fi

# Paso 3: Iniciar en modo producción
echo ""
echo "[PASO 3/4] Iniciando servicios en modo producción..."
docker-compose up -d --build
echo "✅ Servicios iniciados en segundo plano."
echo ""

# Esperar a que los servicios estén listos
echo "⏳ Esperando a que los servicios estén listos..."
sleep 10

# Verificar que la API está respondiendo
echo "🔍 Verificando estado de la API..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API está respondiendo correctamente."
        break
    else
        echo "⏳ Esperando API... (intento $i/30)"
        sleep 2
    fi

    if [ $i -eq 30 ]; then
        echo "❌ ERROR: La API no está respondiendo después de 60 segundos."
        echo "   Revisa los logs con: docker-compose logs api"
        exit 1
    fi
done

# Verificar que Prometheus está funcionando
echo "🔍 Verificando Prometheus..."
for i in {1..15}; do
    if curl -s http://localhost:9090/api/v1/query?query=up > /dev/null 2>&1; then
        echo "✅ Prometheus está funcionando."
        break
    else
        echo "⏳ Esperando Prometheus... (intento $i/15)"
        sleep 2
    fi

    if [ $i -eq 15 ]; then
        echo "⚠️  ADVERTENCIA: Prometheus no está respondiendo. El monitoreo puede estar limitado."
    fi
done

# Verificar que Grafana está funcionando
echo "🔍 Verificando Grafana..."
for i in {1..15}; do
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        echo "✅ Grafana está funcionando."
        break
    else
        echo "⏳ Esperando Grafana... (intento $i/15)"
        sleep 2
    fi

    if [ $i -eq 15 ]; then
        echo "⚠️  ADVERTENCIA: Grafana no está respondiendo. Los dashboards pueden no estar disponibles."
    fi
done

# Paso 4: Monitoreo de logs en tiempo real
echo ""
echo "[PASO 4/4] Mostrando logs en tiempo real de la API. Presiona CTRL+C para salir."
echo "Busca mensajes de inicio exitosos y la ausencia de errores de autenticación."
echo "-----------------------------------------------------"
echo "📊 URLs de monitoreo:"
echo "   - API Health: http://localhost:8000/health"
echo "   - Grafana: http://localhost:3000"
echo "   - Prometheus: http://localhost:9090"
echo "-----------------------------------------------------"
sleep 2 # Espera un par de segundos para que los logs empiecen a fluir
docker-compose logs -f api
