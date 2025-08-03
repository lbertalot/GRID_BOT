#!/bin/bash

# =============================================================================
# Script de Verificación - GridBot Trading Platform
# =============================================================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_message() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Verificación de Configuración${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Verificar Docker
check_docker() {
    if command -v docker &> /dev/null; then
        print_message "Docker está instalado"
        docker_version=$(docker --version)
        print_message "Versión: $docker_version"
    else
        print_error "Docker no está instalado"
        exit 1
    fi
}

# Verificar Docker Compose
check_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        print_message "Docker Compose está instalado"
        compose_version=$(docker-compose --version)
        print_message "Versión: $compose_version"
    else
        print_error "Docker Compose no está instalado"
        exit 1
    fi
}

# Verificar archivos necesarios
check_files() {
    local files=(
        "docker-compose.yml"
        "requirements.txt"
        "env.example"
        "docker/Dockerfile"
        "docker/prometheus/prometheus.yml"
        "docker/nginx/nginx.conf"
        "docker/postgres/init.sql"
    )
    
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            print_message "Archivo encontrado: $file"
        else
            print_error "Archivo faltante: $file"
            exit 1
        fi
    done
}

# Verificar directorios
check_directories() {
    local dirs=(
        "app"
        "docker"
        "scripts"
        "tests"
        "logs"
    )
    
    for dir in "${dirs[@]}"; do
        if [ -d "$dir" ]; then
            print_message "Directorio encontrado: $dir"
        else
            print_warning "Directorio faltante: $dir"
        fi
    done
}

# Verificar variables de entorno
check_env_vars() {
    if [ -f ".env" ]; then
        print_message "Archivo .env encontrado"
        
        # Verificar variables críticas
        local critical_vars=(
            "BINANCE_API_KEY"
            "BINANCE_SECRET_KEY"
            "DATABASE_URL"
            "SECRET_KEY"
        )
        
        for var in "${critical_vars[@]}"; do
            if grep -q "^${var}=" .env; then
                value=$(grep "^${var}=" .env | cut -d'=' -f2)
                if [ "$value" != "" ] && [ "$value" != "your_${var}_here" ]; then
                    print_message "Variable configurada: $var"
                else
                    print_warning "Variable no configurada: $var"
                fi
            else
                print_warning "Variable faltante: $var"
            fi
        done
    else
        print_warning "Archivo .env no encontrado. Ejecuta: cp env.example .env"
    fi
}

# Verificar puertos disponibles
check_ports() {
    local ports=(8000 3000 9090 5555 5432 6379)
    
    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_warning "Puerto $port está en uso"
        else
            print_message "Puerto $port disponible"
        fi
    done
}

# Verificar servicios Docker
check_docker_services() {
    if docker-compose ps | grep -q "Up"; then
        print_message "Servicios Docker están ejecutándose"
        docker-compose ps
    else
        print_warning "No hay servicios Docker ejecutándose"
    fi
}

# Verificar conectividad de red
check_network() {
    if ping -c 1 8.8.8.8 &> /dev/null; then
        print_message "Conectividad de red OK"
    else
        print_error "Sin conectividad de red"
    fi
}

# Verificar recursos del sistema
check_system_resources() {
    # Verificar memoria disponible (macOS compatible)
    if command -v free &> /dev/null; then
        local mem_available=$(free -m | awk 'NR==2{printf "%.0f", $7/1024}')
        if [ "$mem_available" -gt 2 ]; then
            print_message "Memoria disponible: ${mem_available}GB"
        else
            print_warning "Poca memoria disponible: ${mem_available}GB"
        fi
    else
        # macOS fallback
        local mem_total=$(sysctl -n hw.memsize | awk '{print $0/1024/1024/1024}')
        print_message "Memoria total: ${mem_total}GB"
    fi
    
    # Verificar espacio en disco
    local disk_available=$(df -h . | awk 'NR==2{print $4}')
    print_message "Espacio en disco disponible: $disk_available"
}

# Función principal
main() {
    print_header
    
    echo "Verificando requisitos del sistema..."
    check_docker
    check_docker_compose
    check_network
    check_system_resources
    
    echo ""
    echo "Verificando archivos y directorios..."
    check_files
    check_directories
    
    echo ""
    echo "Verificando configuración..."
    check_env_vars
    check_ports
    
    echo ""
    echo "Verificando servicios..."
    check_docker_services
    
    echo ""
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Resumen de Verificación${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
    echo "Si todos los checks pasaron, puedes ejecutar:"
    echo "  ./scripts/start.sh"
    echo ""
    echo "Para más información, consulta el README.md"
}

main "$@" 