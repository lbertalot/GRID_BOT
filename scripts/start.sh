#!/bin/bash

# =============================================================================
# Script de Inicio - GridBot Trading Platform
# =============================================================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir mensajes
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  GridBot Trading Platform${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Función para verificar si Docker está ejecutándose
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker no está ejecutándose. Por favor, inicia Docker Desktop."
        exit 1
    fi
    print_message "Docker está ejecutándose correctamente."
}

# Función para verificar si el archivo .env existe
check_env_file() {
    if [ ! -f .env ]; then
        print_warning "Archivo .env no encontrado. Creando desde .env.example..."
        cp env.example .env
        print_message "Archivo .env creado. Por favor, edita las variables necesarias."
        print_warning "Especialmente BINANCE_API_KEY y BINANCE_SECRET_KEY"
        exit 1
    fi
    print_message "Archivo .env encontrado."
}

# Función para crear directorios necesarios
create_directories() {
    print_message "Creando directorios necesarios..."
    mkdir -p logs
    mkdir -p data
    mkdir -p cache
    mkdir -p static
    print_message "Directorios creados correctamente."
}

# Función para detener contenedores existentes
stop_containers() {
    print_message "Deteniendo contenedores existentes..."
    docker-compose down --remove-orphans
    print_message "Contenedores detenidos."
}

# Función para construir imágenes
build_images() {
    print_message "Construyendo imágenes Docker..."
    docker-compose build --no-cache
    print_message "Imágenes construidas correctamente."
}

# Función para iniciar servicios
start_services() {
    print_message "Iniciando servicios..."
    docker-compose up -d

    # Esperar a que los servicios estén listos
    print_message "Esperando a que los servicios estén listos..."
    sleep 30

    # Verificar estado de los servicios
    check_services_health
}

# Función para verificar la salud de los servicios
check_services_health() {
    print_message "Verificando estado de los servicios..."

    # Verificar API
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        print_message "✅ API está funcionando (http://localhost:8000)"
    else
        print_warning "⚠️  API no responde aún. Puede tardar unos minutos en iniciar."
    fi

    # Verificar Grafana
    if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
        print_message "✅ Grafana está funcionando (http://localhost:3000)"
    else
        print_warning "⚠️  Grafana no responde aún. Puede tardar unos minutos en iniciar."
    fi

    # Verificar Prometheus
    if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
        print_message "✅ Prometheus está funcionando (http://localhost:9090)"
    else
        print_warning "⚠️  Prometheus no responde aún. Puede tardar unos minutos en iniciar."
    fi

    # Verificar Flower
    if curl -f http://localhost:5555 > /dev/null 2>&1; then
        print_message "✅ Flower está funcionando (http://localhost:5555)"
    else
        print_warning "⚠️  Flower no responde aún. Puede tardar unos minutos en iniciar."
    fi
}

# Función para mostrar información de acceso
show_access_info() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Información de Acceso${NC}"
    echo -e "${BLUE}================================${NC}"
    echo -e "${GREEN}🌐 API:${NC} http://localhost:8000"
    echo -e "${GREEN}📊 Grafana:${NC} http://localhost:3000 (admin/gridbot123)"
    echo -e "${GREEN}📈 Prometheus:${NC} http://localhost:9090"
    echo -e "${GREEN}🌸 Flower:${NC} http://localhost:5555"
    echo -e "${GREEN}🔔 Alertmanager:${NC} http://localhost:9093"
    echo -e "${GREEN}📝 Logs:${NC} docker-compose logs -f"
    echo -e "${BLUE}================================${NC}"
}

# Función para mostrar comandos útiles
show_useful_commands() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Comandos Útiles${NC}"
    echo -e "${BLUE}================================${NC}"
    echo -e "${GREEN}📋 Ver logs:${NC} docker-compose logs -f"
    echo -e "${GREEN}🛑 Detener:${NC} docker-compose down"
    echo -e "${GREEN}🔄 Reiniciar:${NC} docker-compose restart"
    echo -e "${GREEN}🧹 Limpiar:${NC} docker-compose down -v --remove-orphans"
    echo -e "${GREEN}🔧 Reconstruir:${NC} docker-compose build --no-cache"
    echo -e "${BLUE}================================${NC}"
}

# Función principal
main() {
    print_header

    # Verificar requisitos
    check_docker
    check_env_file
    create_directories

    # Preguntar si detener contenedores existentes
    if docker-compose ps | grep -q "Up"; then
        read -p "¿Detener contenedores existentes? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            stop_containers
        fi
    fi

    # Preguntar si reconstruir imágenes
    read -p "¿Reconstruir imágenes Docker? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        build_images
    fi

    # Iniciar servicios
    start_services

    # Mostrar información
    show_access_info
    show_useful_commands

    print_message "¡GridBot Trading Platform iniciado correctamente!"
    print_warning "Recuerda configurar tus API keys de Binance en el archivo .env"
}

# Ejecutar función principal
main "$@"
