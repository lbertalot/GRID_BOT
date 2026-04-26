#!/bin/bash

# Script mejorado para configurar el monitoreo de GridBot v2.5 en producción
# Incluye import automático de Grafana y configuración completa

set -e  # Salir en caso de error

echo "====================================================="
echo "== CONFIGURACIÓN AVANZADA DE MONITOREO GRIDBOT V2.5 =="
echo "====================================================="
echo ""

# Función para esperar que un servicio esté disponible
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1

    echo "⏳ Esperando que $service_name esté disponible..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo "✅ $service_name está disponible."
            return 0
        fi
        echo "   Intento $attempt/$max_attempts - Esperando 2 segundos..."
        sleep 2
        ((attempt++))
    done

    echo "❌ ERROR: $service_name no está disponible después de $max_attempts intentos"
    return 1
}

# Función para importar dashboard en Grafana
import_grafana_dashboard() {
    local dashboard_file=$1
    local dashboard_name=$2

    echo "📊 Importando dashboard: $dashboard_name"

    # Obtener el token de API de Grafana (usando credenciales por defecto)
    local grafana_url="http://localhost:3000"
    local username="admin"
    local password="gridbot123"

    # Crear token de API
    local api_key=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d '{"name":"gridbot-monitoring","role":"Admin"}' \
        "$grafana_url/api/auth/keys" \
        -u "$username:$password" 2>/dev/null | jq -r '.key' 2>/dev/null || echo "")

    if [ -z "$api_key" ] || [ "$api_key" = "null" ]; then
        echo "⚠️  No se pudo crear token de API, usando importación manual"
        return 1
    fi

    # Importar dashboard
    local dashboard_json=$(cat "$dashboard_file")
    local import_response=$(curl -s -X POST \
        -H "Authorization: Bearer $api_key" \
        -H "Content-Type: application/json" \
        -d "$dashboard_json" \
        "$grafana_url/api/dashboards/db" 2>/dev/null)

    if echo "$import_response" | jq -e '.id' > /dev/null 2>&1; then
        local dashboard_id=$(echo "$import_response" | jq -r '.id')
        echo "✅ Dashboard importado exitosamente (ID: $dashboard_id)"
        echo "   URL: $grafana_url/d/$dashboard_id"
        return 0
    else
        echo "⚠️  Error importando dashboard: $import_response"
        return 1
    fi
}

# Verificar que los servicios estén funcionando
echo "[PASO 1/4] Verificando servicios de monitoreo..."

# Verificar Prometheus
if ! wait_for_service "http://localhost:9090/api/v1/query?query=up" "Prometheus"; then
    echo "   Iniciando Prometheus..."
    docker-compose up -d prometheus
    wait_for_service "http://localhost:9090/api/v1/query?query=up" "Prometheus"
fi

# Verificar Grafana
if ! wait_for_service "http://localhost:3000/api/health" "Grafana"; then
    echo "   Iniciando Grafana..."
    docker-compose up -d grafana
    wait_for_service "http://localhost:3000/api/health" "Grafana"
fi

# Verificar Alertmanager
if ! wait_for_service "http://localhost:9093/api/v1/status" "Alertmanager"; then
    echo "   Iniciando Alertmanager..."
    docker-compose up -d alertmanager
    wait_for_service "http://localhost:9093/api/v1/status" "Alertmanager"
fi

echo ""

# Configurar reglas de Prometheus
echo "[PASO 2/4] Configurando reglas de alerta de Prometheus..."

if [ -f "gridbot.rules.yml" ]; then
    # Copiar reglas a Prometheus
    docker cp gridbot.rules.yml gridbot_prometheus:/etc/prometheus/rules/
    echo "✅ Reglas de alerta copiadas a Prometheus."

    # Recargar configuración de Prometheus
    curl -X POST http://localhost:9090/-/reload
    echo "✅ Configuración de Prometheus recargada."
else
    echo "❌ ERROR: No se encontró el archivo gridbot.rules.yml"
    exit 1
fi

echo ""

# Configurar datasource de Prometheus en Grafana
echo "[PASO 3/4] Configurando datasource de Prometheus en Grafana..."

# Esperar a que Grafana esté completamente iniciado
sleep 10

# Crear datasource de Prometheus
curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Prometheus",
        "type": "prometheus",
        "url": "http://prometheus:9090",
        "access": "proxy",
        "isDefault": true,
        "jsonData": {
            "httpMethod": "POST"
        }
    }' \
    http://localhost:3000/api/datasources \
    -u admin:gridbot123 > /dev/null 2>&1

echo "✅ Datasource de Prometheus configurado en Grafana."

echo ""

# Importar dashboards de Grafana
echo "[PASO 4/4] Importando dashboards de Grafana..."

if [ -f "grafana-roi-dashboard.json" ]; then
    if import_grafana_dashboard "grafana-roi-dashboard.json" "GridBot ROI Dashboard"; then
        echo "✅ Dashboard de ROI importado automáticamente."
    else
        echo "⚠️  Importación automática falló, usando método manual:"
        echo "   1. Abre http://localhost:3000 en tu navegador"
        echo "   2. Usuario: admin, Contraseña: gridbot123"
        echo "   3. Ve a Dashboards > Import"
        echo "   4. Copia y pega el contenido de grafana-roi-dashboard.json"
        echo "   5. Ajusta el capital inicial (18.47 USDT) en el panel de ROI"
    fi
else
    echo "❌ ERROR: No se encontró el archivo grafana-roi-dashboard.json"
    exit 1
fi

echo ""

# Configurar monitoreo continuo
echo "🔧 Configurando monitoreo continuo..."

if [ -f "scripts/continuous_monitoring.py" ]; then
    chmod +x scripts/continuous_monitoring.py
    echo "✅ Script de monitoreo continuo configurado."
    echo "   Para iniciar: python3 scripts/continuous_monitoring.py"
else
    echo "⚠️  Script de monitoreo continuo no encontrado."
fi

echo ""

# Crear directorio de logs si no existe
mkdir -p logs
echo "✅ Directorio de logs configurado."

echo ""
echo "🎉 Configuración de monitoreo completada!"
echo ""
echo "📊 URLs de monitoreo:"
echo "   - Grafana: http://localhost:3000 (admin/gridbot123)"
echo "   - Prometheus: http://localhost:9090"
echo "   - Alertmanager: http://localhost:9093"
echo ""
echo "🔍 Métricas clave a monitorear:"
echo "   - PnL Acumulado: sum(gridbot_trade_pnl_usdt_total)"
echo "   - ROI: (sum(gridbot_trade_pnl_usdt_total) / 18.47) * 100"
echo "   - Win Rate: (sum(gridbot_trades_successful_total) / sum(gridbot_trades_executed_total)) * 100"
echo "   - Circuit Breakers: sum(gridbot_circuit_breakers_active_total)"
echo ""
echo "🚀 Para iniciar monitoreo continuo:"
echo "   python3 scripts/continuous_monitoring.py"
echo ""
echo "⚠️  RECORDATORIO: Ajusta el capital inicial (18.47 USDT) en el dashboard de Grafana"
echo "   según tu capital real antes de comenzar el trading."
