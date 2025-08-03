#!/bin/bash

# Script de configuración automática para GridBot Trading
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
    echo -e "${BLUE}  GridBot Trading Setup v2.0${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Función para validar archivo .env
validate_env_file() {
    print_message "Validando archivo de configuración..."
    
    if [ ! -f ".env" ]; then
        print_error "Archivo .env no encontrado"
        print_message "Copiando archivo de ejemplo..."
        cp env.example .env
        print_warning "Por favor, edita el archivo .env con tus credenciales"
        return 1
    fi
    
    # Verificar variables críticas
    local missing_vars=()
    
    if ! grep -q "BINANCE_API_KEY=" .env || grep -q "BINANCE_API_KEY=your_" .env; then
        missing_vars+=("BINANCE_API_KEY")
    fi
    
    if ! grep -q "BINANCE_SECRET_KEY=" .env || grep -q "BINANCE_SECRET_KEY=your_" .env; then
        missing_vars+=("BINANCE_SECRET_KEY")
    fi
    
    if ! grep -q "TELEGRAM_BOT_TOKEN=" .env || grep -q "TELEGRAM_BOT_TOKEN=your_" .env; then
        missing_vars+=("TELEGRAM_BOT_TOKEN")
    fi
    
    if ! grep -q "TELEGRAM_CHAT_ID=" .env || grep -q "TELEGRAM_CHAT_ID=your_" .env; then
        missing_vars+=("TELEGRAM_CHAT_ID")
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_error "Variables faltantes en .env:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        print_warning "Por favor, configura estas variables antes de continuar"
        return 1
    fi
    
    print_message "Archivo .env validado correctamente"
    return 0
}

# Función para verificar servicios Docker
check_docker_services() {
    print_message "Verificando servicios Docker..."
    
    if ! docker-compose ps | grep -q "Up"; then
        print_warning "Servicios Docker no están ejecutándose"
        print_message "Iniciando servicios..."
        docker-compose up -d
        
        # Esperar a que los servicios estén listos
        print_message "Esperando a que los servicios estén listos..."
        sleep 30
    fi
    
    # Verificar que la API responde
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        print_message "API funcionando correctamente"
    else
        print_error "API no responde"
        return 1
    fi
    
    return 0
}

# Función para probar conexión con Binance
test_binance_connection() {
    print_message "Probando conexión con Binance..."
    
    # Cargar variables de entorno
    source .env
    
    # Hacer request a la API para probar Binance
    response=$(curl -s -X GET "http://localhost:8000/api/v1/test/binance")
    
    if echo "$response" | grep -q "success"; then
        print_message "Conexión con Binance exitosa"
        return 0
    else
        print_error "Error conectando con Binance"
        print_warning "Verifica tus API Keys en el archivo .env"
        return 1
    fi
}

# Función para probar Telegram
test_telegram() {
    print_message "Probando notificaciones de Telegram..."
    
    response=$(curl -s -X POST "http://localhost:8000/api/v1/test/telegram")
    
    if echo "$response" | grep -q "success"; then
        print_message "Telegram configurado correctamente"
        print_message "Deberías recibir un mensaje de prueba en Telegram"
        return 0
    else
        print_error "Error enviando mensaje a Telegram"
        print_warning "Verifica tu bot token y chat ID en el archivo .env"
        return 1
    fi
}

# Función para obtener balance de Binance
get_binance_balance() {
    print_message "Obteniendo balance de Binance..."
    
    response=$(curl -s "http://localhost:8000/api/v1/balance")
    
    if echo "$response" | grep -q "balance"; then
        print_message "Balance obtenido correctamente"
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
    else
        print_warning "No se pudo obtener el balance"
    fi
}

# Función para iniciar trading
start_trading() {
    print_message "Iniciando trading automático..."
    
    response=$(curl -s -X POST "http://localhost:8000/api/v1/trading/start")
    
    if echo "$response" | grep -q "success"; then
        print_message "Trading iniciado correctamente"
        print_message "GridBot está ahora operativo y ejecutando órdenes"
        return 0
    else
        print_error "Error iniciando trading"
        echo "$response"
        return 1
    fi
}

# Función para mostrar estado del sistema
show_system_status() {
    print_message "Estado del sistema:"
    
    echo -e "${BLUE}Servicios Docker:${NC}"
    docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    
    echo -e "\n${BLUE}API Status:${NC}"
    curl -s http://localhost:8000/health | jq '.' 2>/dev/null || curl -s http://localhost:8000/health
    
    echo -e "\n${BLUE}Interfaces disponibles:${NC}"
    echo "  - Dashboard: http://localhost:8000"
    echo "  - Grafana: http://localhost:3000 (admin/gridbot123)"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Flower: http://localhost:5555"
}

# Función para mostrar comandos útiles
show_useful_commands() {
    echo -e "\n${BLUE}Comandos útiles:${NC}"
    echo "  # Ver logs en tiempo real:"
    echo "  docker-compose logs -f api"
    echo ""
    echo "  # Ver métricas de trading:"
    echo "  curl http://localhost:8000/api/v1/metrics"
    echo ""
    echo "  # Detener trading:"
    echo "  curl -X POST http://localhost:8000/api/v1/trading/stop"
    echo ""
    echo "  # Ver configuración:"
    echo "  curl http://localhost:8000/api/v1/config"
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
    
    # Validar archivo .env
    if ! validate_env_file; then
        print_error "Configuración incompleta. Por favor, edita el archivo .env"
        exit 1
    fi
    
    # Verificar servicios Docker
    if ! check_docker_services; then
        print_error "Error con servicios Docker"
        exit 1
    fi
    
    # Probar conexión con Binance
    if ! test_binance_connection; then
        print_warning "No se pudo conectar con Binance"
        print_warning "El sistema funcionará en modo simulación"
    fi
    
    # Probar Telegram
    if ! test_telegram; then
        print_warning "Telegram no configurado correctamente"
        print_warning "No recibirás notificaciones"
    fi
    
    # Obtener balance
    get_binance_balance
    
    # Preguntar si iniciar trading
    echo -e "\n${YELLOW}¿Deseas iniciar el trading automático ahora? (y/n)${NC}"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        if start_trading; then
            print_message "¡GridBot está ahora operativo!"
        else
            print_error "No se pudo iniciar el trading"
        fi
    else
        print_message "Trading no iniciado. Puedes iniciarlo manualmente más tarde"
    fi
    
    # Mostrar estado del sistema
    show_system_status
    
    # Mostrar comandos útiles
    show_useful_commands
    
    echo -e "\n${GREEN}¡Configuración completada!${NC}"
    echo -e "${BLUE}Consulta la guía de usuario para más información${NC}"
}

# Ejecutar función principal
main "$@" 