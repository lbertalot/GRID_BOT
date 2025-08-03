#!/bin/bash

# Script para aplicar mejoras en el stack de monitoreo y base de datos
# Uso: ./scripts/apply_monitoring_improvements.sh [--tls]

set -e

echo "🔧 Aplicando mejoras en el stack de monitoreo y base de datos..."

# Verificar si se solicita TLS
TLS_MODE=false
if [[ "$1" == "--tls" ]]; then
    TLS_MODE=true
    echo "🔐 Modo TLS habilitado"
fi

# Función para verificar dependencias
check_dependencies() {
    echo "📋 Verificando dependencias..."
    
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker no está instalado"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose no está instalado"
        exit 1
    fi
    
    if ! command -v openssl &> /dev/null; then
        echo "❌ OpenSSL no está instalado"
        exit 1
    fi
    
    echo "✅ Dependencias verificadas"
}

# Función para generar certificados TLS
generate_tls_certs() {
    if [[ "$TLS_MODE" == true ]]; then
        echo "🔐 Generando certificados TLS..."
        
        # Crear directorio de certificados
        mkdir -p docker/ssl/certs
        
        # Generar certificados
        chmod +x docker/ssl/generate-certs.sh
        ./docker/ssl/generate-certs.sh
        
        echo "✅ Certificados TLS generados"
    fi
}

# Función para detener servicios actuales
stop_current_services() {
    echo "🛑 Deteniendo servicios actuales..."
    
    if docker-compose ps | grep -q "Up"; then
        docker-compose down
        echo "✅ Servicios detenidos"
    else
        echo "ℹ️  No hay servicios ejecutándose"
    fi
}

# Función para limpiar volúmenes (opcional)
clean_volumes() {
    read -p "¿Deseas limpiar los volúmenes de datos? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🧹 Limpiando volúmenes..."
        docker-compose down -v
        docker volume prune -f
        echo "✅ Volúmenes limpiados"
    fi
}

# Función para construir imágenes
build_images() {
    echo "🔨 Construyendo imágenes Docker..."
    
    # Construir imagen de PostgreSQL personalizada
    echo "📦 Construyendo imagen de PostgreSQL..."
    docker build -t gridbot-postgres:latest ./docker/postgres
    
    # Construir imagen principal
    echo "📦 Construyendo imagen principal..."
    docker-compose build --no-cache
    
    echo "✅ Imágenes construidas"
}

# Función para iniciar servicios
start_services() {
    echo "🚀 Iniciando servicios..."
    
    if [[ "$TLS_MODE" == true ]]; then
        echo "🔐 Iniciando con configuración TLS..."
        docker-compose -f docker-compose.tls.yml up -d
    else
        echo "🔓 Iniciando con configuración estándar..."
        docker-compose up -d
    fi
    
    echo "✅ Servicios iniciados"
}

# Función para verificar servicios
verify_services() {
    echo "🔍 Verificando servicios..."
    
    # Esperar a que los servicios estén listos
    echo "⏳ Esperando a que los servicios estén listos..."
    sleep 30
    
    # Verificar PostgreSQL
    echo "🗄️  Verificando PostgreSQL..."
    if docker-compose exec -T db pg_isready -U griduser -d gridbot; then
        echo "✅ PostgreSQL funcionando correctamente"
    else
        echo "❌ Error en PostgreSQL"
        return 1
    fi
    
    # Verificar Grafana
    echo "📊 Verificando Grafana..."
    if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
        echo "✅ Grafana funcionando correctamente"
    else
        echo "❌ Error en Grafana"
        return 1
    fi
    
    # Verificar Prometheus
    echo "📈 Verificando Prometheus..."
    if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
        echo "✅ Prometheus funcionando correctamente"
    else
        echo "❌ Error en Prometheus"
        return 1
    fi
    
    # Verificar Alertmanager
    echo "🚨 Verificando Alertmanager..."
    if curl -f http://localhost:9093/-/healthy > /dev/null 2>&1; then
        echo "✅ Alertmanager funcionando correctamente"
    else
        echo "❌ Error en Alertmanager"
        return 1
    fi
    
    echo "✅ Todos los servicios verificados"
}

# Función para mostrar logs de errores
show_error_logs() {
    echo "📋 Mostrando logs de errores..."
    
    echo "📄 Logs de PostgreSQL:"
    docker-compose logs db | tail -20
    
    echo "📄 Logs de Grafana:"
    docker-compose logs grafana | tail -20
    
    echo "📄 Logs de Prometheus:"
    docker-compose logs prometheus | tail -20
    
    echo "📄 Logs de Alertmanager:"
    docker-compose logs alertmanager | tail -20
}

# Función para mostrar resumen
show_summary() {
    echo ""
    echo "🎉 ¡Mejoras aplicadas exitosamente!"
    echo ""
    echo "📊 Resumen de mejoras:"
    echo "   ✅ PostgreSQL: Locale configurado (en_US.UTF-8)"
    echo "   ✅ Grafana: Base de datos PostgreSQL configurada"
    echo "   ✅ Alertmanager: Receptor slack no utilizado eliminado"
    if [[ "$TLS_MODE" == true ]]; then
        echo "   ✅ TLS: Certificados generados y configurados"
    fi
    echo "   ✅ Volúmenes: Persistencia configurada"
    echo "   ✅ Health checks: Configurados para todos los servicios"
    echo ""
    echo "🌐 Servicios disponibles:"
    echo "   • API: http://localhost:8000"
    echo "   • Grafana: http://localhost:3000 (admin/admin)"
    echo "   • Prometheus: http://localhost:9090"
    echo "   • Alertmanager: http://localhost:9093"
    echo "   • Flower: http://localhost:5555"
    echo ""
    if [[ "$TLS_MODE" == true ]]; then
        echo "🔐 TLS habilitado:"
        echo "   • Certificados autofirmados generados"
        echo "   • Comunicación segura entre servicios"
        echo "   • Para producción, reemplazar con certificados de Let's Encrypt"
    fi
    echo ""
    echo "📋 Comandos útiles:"
    echo "   • Ver logs: docker-compose logs -f [servicio]"
    echo "   • Verificar estado: docker-compose ps"
    echo "   • Reiniciar: docker-compose restart"
    echo "   • Detener: docker-compose down"
}

# Función principal
main() {
    echo "🚀 Aplicando mejoras en el stack de monitoreo y base de datos"
    echo "============================================================"
    
    check_dependencies
    generate_tls_certs
    stop_current_services
    clean_volumes
    build_images
    start_services
    
    # Verificar servicios
    if verify_services; then
        show_summary
    else
        echo "❌ Error en la verificación de servicios"
        show_error_logs
        exit 1
    fi
}

# Ejecutar función principal
main "$@" 