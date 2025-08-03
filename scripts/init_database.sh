#!/bin/bash

# Script para inicializar la base de datos de GridBot
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
    echo -e "${BLUE}  GridBot Database Initialization${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Función para verificar que Docker está ejecutándose
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker no está ejecutándose"
        exit 1
    fi
}

# Función para verificar que los servicios están ejecutándose
check_services() {
    print_message "Verificando servicios Docker..."
    
    if ! docker-compose ps | grep -q "Up"; then
        print_warning "Servicios Docker no están ejecutándose"
        print_message "Iniciando servicios..."
        docker-compose up -d db
        sleep 10
    fi
    
    # Verificar que la base de datos está lista
    print_message "Esperando a que la base de datos esté lista..."
    max_retries=30
    retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if docker-compose exec -T db pg_isready -U griduser > /dev/null 2>&1; then
            print_message "Base de datos lista"
            break
        fi
        retry_count=$((retry_count + 1))
        print_message "Esperando base de datos... ($retry_count/$max_retries)"
        sleep 2
    done
    
    if [ $retry_count -eq $max_retries ]; then
        print_error "La base de datos no está disponible después de $max_retries intentos"
        exit 1
    fi
}

# Función para ejecutar la inicialización
init_database() {
    print_message "Inicializando base de datos..."
    
    # Ejecutar el script de inicialización
    docker-compose exec -T api python -m app.db.init_db
    
    if [ $? -eq 0 ]; then
        print_message "Base de datos inicializada correctamente"
    else
        print_error "Error inicializando la base de datos"
        exit 1
    fi
}

# Función para verificar las tablas
verify_tables() {
    print_message "Verificando tablas creadas..."
    
    # Verificar que las tablas existen
    tables=$(docker-compose exec -T db psql -U griduser -d gridbot -t -c "
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('grid_config', 'asset_limits', 'trades', 'performance_metrics', 'alerts', 'system_config')
        ORDER BY table_name;
    " 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        print_message "Tablas verificadas:"
        echo "$tables" | while read table; do
            if [ ! -z "$table" ]; then
                echo "  ✅ $table"
            fi
        done
    else
        print_warning "No se pudieron verificar las tablas"
    fi
}

# Función para mostrar datos de ejemplo
show_sample_data() {
    print_message "Mostrando datos de ejemplo..."
    
    # Mostrar configuración del grid
    echo -e "\n${BLUE}Configuración del Grid:${NC}"
    docker-compose exec -T db psql -U griduser -d gridbot -c "
        SELECT trading_pair, grid_levels, min_price, max_price, quantity_per_trade 
        FROM grid_config;
    " 2>/dev/null || echo "  No se pudieron mostrar los datos"
    
    # Mostrar configuración del sistema
    echo -e "\n${BLUE}Configuración del Sistema:${NC}"
    docker-compose exec -T db psql -U griduser -d gridbot -c "
        SELECT key, value, description 
        FROM system_config;
    " 2>/dev/null || echo "  No se pudieron mostrar los datos"
}

# Función principal
main() {
    print_header
    
    # Verificar que estamos en el directorio correcto
    if [ ! -f "docker-compose.yml" ]; then
        print_error "No se encontró docker-compose.yml"
        print_error "Ejecuta este script desde el directorio del proyecto"
        exit 1
    fi
    
    # Verificar Docker
    check_docker
    
    # Verificar servicios
    check_services
    
    # Inicializar base de datos
    init_database
    
    # Verificar tablas
    verify_tables
    
    # Mostrar datos de ejemplo
    show_sample_data
    
    print_message "¡Inicialización de base de datos completada!"
    print_message "El sistema está listo para usar"
}

# Ejecutar función principal
main "$@" 