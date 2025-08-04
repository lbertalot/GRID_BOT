#!/bin/bash

# Script para reiniciar el proyecto Grid Trading Bot desde cero
# Incluye todas las mejoras y optimizaciones dockerizadas

set -e

echo "🚀 Reiniciando Grid Trading Bot desde cero"
echo "=========================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir con colores
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Función para limpiar Docker
cleanup_docker() {
    print_status "Limpiando contenedores y volúmenes Docker..."
    
    # Detener y eliminar contenedores
    docker-compose down -v 2>/dev/null || true
    
    # Limpiar imágenes no utilizadas
    docker system prune -a -f
    
    # Limpiar volúmenes no utilizados
    docker volume prune -f
    
    # Limpiar redes no utilizadas
    docker network prune -f
    
    print_success "Docker limpiado completamente"
}

# Función para verificar dependencias
check_dependencies() {
    print_status "Verificando dependencias del sistema..."
    
    # Verificar Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker no está instalado"
        exit 1
    fi
    
    # Verificar Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose no está instalado"
        exit 1
    fi
    
    # Verificar que Docker esté ejecutándose
    if ! docker info &> /dev/null; then
        print_error "Docker no está ejecutándose"
        exit 1
    fi
    
    print_success "Dependencias verificadas"
}

# Función para verificar archivos necesarios
check_files() {
    print_status "Verificando archivos necesarios..."
    
    required_files=(
        "Dockerfile"
        "docker-compose.yml"
        "requirements.txt"
        ".env"
        "app/main_simple.py"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            print_error "Archivo requerido no encontrado: $file"
            exit 1
        fi
    done
    
    print_success "Archivos necesarios verificados"
}

# Función para crear directorios necesarios
create_directories() {
    print_status "Creando directorios necesarios..."
    
    directories=(
        "logs"
        "cache"
        "data"
        "docker/postgres"
        "docker/prometheus"
        "docker/grafana"
        "docker/alertmanager"
        "docker/nginx"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
    done
    
    print_success "Directorios creados"
}

# Función para construir imágenes Docker
build_images() {
    print_status "Construyendo imágenes Docker..."
    
    # Construir imagen principal
    docker-compose build --no-cache
    
    print_success "Imágenes construidas correctamente"
}

# Función para iniciar servicios
start_services() {
    print_status "Iniciando servicios..."
    
    # Iniciar servicios en modo detached
    docker-compose up -d
    
    print_success "Servicios iniciados"
}

# Función para verificar estado de servicios
check_services() {
    print_status "Verificando estado de servicios..."
    
    # Esperar un poco para que los servicios se inicien
    sleep 10
    
    # Verificar contenedores
    containers_status=$(docker-compose ps)
    echo "$containers_status"
    
    # Verificar servicios críticos
    critical_services=("db" "redis" "api")
    
    for service in "${critical_services[@]}"; do
        if docker-compose ps | grep -q "$service.*Up"; then
            print_success "Servicio $service está ejecutándose"
        else
            print_error "Servicio $service no está ejecutándose"
            return 1
        fi
    done
    
    print_success "Todos los servicios críticos están ejecutándose"
}

# Función para mostrar información de acceso
show_access_info() {
    echo ""
    echo "🎉 ¡Proyecto reiniciado exitosamente!"
    echo "====================================="
    echo ""
    echo "📊 Servicios disponibles:"
    echo "   • API Principal: http://localhost:8000"
    echo "   • Grafana: http://localhost:3000 (admin/gridbot123)"
    echo "   • Prometheus: http://localhost:9090"
    echo "   • Flower (Celery): http://localhost:5555"
    echo "   • Alertmanager: http://localhost:9093"
    echo "   • Nginx: http://localhost:80"
    echo ""
    echo "🗄️  Base de datos:"
    echo "   • PostgreSQL: localhost:5432"
    echo "   • Redis: localhost:6379"
    echo ""
    echo "🔧 Comandos útiles:"
    echo "   • Ver logs: docker-compose logs -f api"
    echo "   • Ver estado: docker-compose ps"
    echo "   • Detener: docker-compose down"
    echo "   • Reiniciar: docker-compose restart"
    echo ""
    echo "📋 Configuraciones aplicadas:"
    echo "   • WebSocket avanzado: Disponible (deshabilitado por defecto)"
    echo "   • Paper Trading: Habilitado"
    echo "   • Binance Testnet: Habilitado"
    echo "   • Monitoreo: Prometheus + Grafana"
    echo "   • Cache: Redis optimizado"
    echo ""
}

# Función principal
main() {
    echo "🔄 Iniciando reinicio completo del proyecto..."
    echo ""
    
    # Verificar dependencias
    check_dependencies
    
    # Limpiar Docker
    cleanup_docker
    
    # Verificar archivos
    check_files
    
    # Crear directorios
    create_directories
    
    # Construir imágenes
    build_images
    
    # Iniciar servicios
    start_services
    
    # Verificar servicios
    if check_services; then
        show_access_info
        print_success "¡Reinicio completado exitosamente!"
    else
        print_error "Error verificando servicios"
        exit 1
    fi
}

# Manejo de errores
trap 'print_error "Error en línea $LINENO. Saliendo..."; exit 1' ERR

# Ejecutar función principal
main "$@" 