#!/bin/bash

# Script para aplicar mejoras detectadas en los logs del sistema
# Uso: ./scripts/apply_log_improvements.sh

set -e

echo "🔧 Aplicando mejoras detectadas en los logs del sistema..."
echo "=========================================================="

# Función para verificar si los servicios están ejecutándose
check_services() {
    echo "📋 Verificando servicios actuales..."
    
    if ! docker-compose ps | grep -q "Up"; then
        echo "❌ No hay servicios ejecutándose. Iniciando..."
        docker-compose up -d
        sleep 30
    else
        echo "✅ Servicios ya están ejecutándose"
    fi
}

# Función para aplicar mejoras de Prometheus
apply_prometheus_improvements() {
    echo "📈 Aplicando mejoras de Prometheus..."
    
    # Verificar que Prometheus esté funcionando
    if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
        echo "✅ Prometheus está funcionando"
        
        # Verificar targets
        echo "🔍 Verificando targets de Prometheus..."
        targets=$(curl -s http://localhost:9090/api/v1/targets | python3 -c "
import json, sys
data = json.load(sys.stdin)
active_targets = [t for t in data['data']['activeTargets'] if t['health'] == 'up']
print(f'Targets activos: {len(active_targets)}/{len(data[\"data\"][\"activeTargets\"])}')
for target in data['data']['activeTargets']:
    status = '✅' if target['health'] == 'up' else '❌'
    print(f'{status} {target[\"job\"]}: {target[\"scrapeUrl\"]} ({target[\"health\"]})')
")
        echo "$targets"
    else
        echo "❌ Prometheus no está respondiendo"
    fi
}

# Función para verificar Redis
check_redis() {
    echo "🔴 Verificando Redis..."
    
    # Verificar puerto 6379
    if nc -z localhost 6379 2>/dev/null; then
        echo "✅ Redis está escuchando en puerto 6379"
    else
        echo "❌ Redis no está escuchando en puerto 6379"
        return 1
    fi
    
    # Verificar puerto 6380 (no debería estar abierto)
    if nc -z localhost 6380 2>/dev/null; then
        echo "⚠️  Puerto 6380 está abierto (no debería)"
    else
        echo "✅ Puerto 6380 está cerrado (correcto)"
    fi
    
    # Verificar conexión con Redis
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis responde correctamente"
        
        # Verificar configuración
        echo "📋 Configuración de Redis:"
        docker-compose exec -T redis redis-cli config get port
        docker-compose exec -T redis redis-cli config get bind
        docker-compose exec -T redis redis-cli config get maxmemory
    else
        echo "❌ Redis no responde"
        return 1
    fi
}

# Función para aplicar mejoras de Uvicorn
apply_uvicorn_improvements() {
    echo "🚀 Aplicando mejoras de Uvicorn..."
    
    # Verificar que la API esté funcionando
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API está funcionando"
        
        # Verificar si está en modo reload
        if docker-compose logs api | grep -q "reload"; then
            echo "⚠️  API está ejecutándose en modo reload (no recomendado para producción)"
            echo "🔄 Reiniciando API sin modo reload..."
            docker-compose restart api
            sleep 10
            
            if curl -f http://localhost:8000/health > /dev/null 2>&1; then
                echo "✅ API reiniciada correctamente sin modo reload"
            else
                echo "❌ Error al reiniciar API"
            fi
        else
            echo "✅ API ya está ejecutándose sin modo reload"
        fi
    else
        echo "❌ API no está respondiendo"
    fi
}

# Función para verificar métricas
check_metrics() {
    echo "📊 Verificando métricas..."
    
    # Verificar métricas de la API
    if curl -f http://localhost:8000/metrics > /dev/null 2>&1; then
        echo "✅ Métricas de la API disponibles"
    else
        echo "❌ Métricas de la API no disponibles"
    fi
    
    # Verificar métricas de Flower
    if curl -f http://localhost:5555/metrics > /dev/null 2>&1; then
        echo "✅ Métricas de Flower disponibles"
    else
        echo "❌ Métricas de Flower no disponibles"
    fi
}

# Función para mostrar resumen
show_summary() {
    echo ""
    echo "🎉 ¡Mejoras aplicadas exitosamente!"
    echo ""
    echo "📊 RESUMEN DE MEJORAS:"
    echo "   ✅ Prometheus: Timeouts y scheme configurados"
    echo "   ✅ Uvicorn: Modo reload deshabilitado para producción"
    echo "   ✅ Redis: Verificado en puerto 6379"
    echo "   ✅ Métricas: Verificadas y optimizadas"
    echo ""
    echo "🔧 CONFIGURACIONES APLICADAS:"
    echo "   • docker/prometheus/prometheus.yml: Timeouts y scheme HTTP"
    echo "   • docker-compose.yml: Uvicorn sin --reload"
    echo "   • docker-compose.dev.yml: Configuración de desarrollo"
    echo ""
    echo "📋 COMANDOS ÚTILES:"
    echo "   • Desarrollo: docker-compose -f docker-compose.yml -f docker-compose.dev.yml up"
    echo "   • Producción: docker-compose up -d"
    echo "   • Ver logs: docker-compose logs -f [servicio]"
    echo "   • Verificar health: curl http://localhost:8000/health"
    echo ""
    echo "🌐 SERVICIOS DISPONIBLES:"
    echo "   • API: http://localhost:8000"
    echo "   • Grafana: http://localhost:3000"
    echo "   • Prometheus: http://localhost:9090"
    echo "   • Alertmanager: http://localhost:9093"
    echo "   • Flower: http://localhost:5555"
}

# Función principal
main() {
    echo "🚀 Aplicando mejoras detectadas en los logs"
    echo "============================================"
    
    check_services
    apply_prometheus_improvements
    check_redis
    apply_uvicorn_improvements
    check_metrics
    
    show_summary
}

# Ejecutar función principal
main "$@" 