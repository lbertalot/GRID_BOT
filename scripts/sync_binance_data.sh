#!/bin/bash

# Script para sincronizar datos reales de Binance con la base de datos
# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
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
    echo -e "${BLUE}  Binance Data Synchronization${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_section() {
    echo -e "${PURPLE}--- $1 ---${NC}"
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
        docker-compose up -d
        sleep 15
    fi
    
    # Verificar que la API está lista
    print_message "Esperando a que la API esté lista..."
    max_retries=30
    retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            print_message "API lista"
            break
        fi
        retry_count=$((retry_count + 1))
        print_message "Esperando API... ($retry_count/$max_retries)"
        sleep 2
    done
    
    if [ $retry_count -eq $max_retries ]; then
        print_error "La API no está disponible después de $max_retries intentos"
        exit 1
    fi
}

# Función para verificar credenciales de Binance
check_binance_credentials() {
    print_section "Verificación de Credenciales"
    
    # Verificar archivo .env
    if [ ! -f ".env" ]; then
        print_error "Archivo .env no encontrado"
        print_message "Crea el archivo .env con tus credenciales de Binance"
        exit 1
    fi
    
    # Verificar variables de entorno
    source .env
    
    if [ -z "$BINANCE_API_KEY" ] || [ "$BINANCE_API_KEY" = "your_binance_api_key_here" ]; then
        print_error "BINANCE_API_KEY no configurada en .env"
        exit 1
    fi
    
    if [ -z "$BINANCE_SECRET_KEY" ] || [ "$BINANCE_SECRET_KEY" = "your_binance_secret_key_here" ]; then
        print_error "BINANCE_SECRET_KEY no configurada en .env"
        exit 1
    fi
    
    print_message "✅ Credenciales de Binance configuradas"
}

# Función para probar conexión con Binance
test_binance_connection() {
    print_section "Prueba de Conexión"
    
    print_message "Probando conexión con Binance..."
    
    response=$(curl -s -X GET "http://localhost:8000/api/v1/test/binance")
    
    if echo "$response" | grep -q '"status":"success"'; then
        print_message "✅ Conexión con Binance exitosa"
        return 0
    else
        print_error "❌ Error conectando con Binance"
        echo "$response" | jq . 2>/dev/null || echo "$response"
        return 1
    fi
}

# Función para sincronizar información de cuenta
sync_account_info() {
    print_section "Sincronización de Información de Cuenta"
    
    print_message "Sincronizando información de cuenta..."
    
    response=$(curl -s -X POST "http://localhost:8000/api/v1/binance/sync/account")
    
    if echo "$response" | grep -q '"status":"success"'; then
        print_message "✅ Información de cuenta sincronizada"
        echo "$response" | jq '.data' 2>/dev/null || echo "$response"
    else
        print_error "❌ Error sincronizando información de cuenta"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    fi
}

# Función para sincronizar balances
sync_balances() {
    print_section "Sincronización de Balances"
    
    print_message "Sincronizando balances..."
    
    response=$(curl -s -X POST "http://localhost:8000/api/v1/binance/sync/balances")
    
    if echo "$response" | grep -q '"status":"success"'; then
        print_message "✅ Balances sincronizados"
        data=$(echo "$response" | jq -r '.data.balances_count // "N/A"')
        total_value=$(echo "$response" | jq -r '.data.total_value_usdt // "N/A"')
        print_message "   Activos con saldo: $data"
        print_message "   Valor total (USDT): $total_value"
    else
        print_error "❌ Error sincronizando balances"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    fi
}

# Función para sincronizar información de símbolos
sync_symbols() {
    print_section "Sincronización de Símbolos"
    
    print_message "Sincronizando información de símbolos..."
    
    response=$(curl -s -X POST "http://localhost:8000/api/v1/binance/sync/symbols")
    
    if echo "$response" | grep -q '"status":"success"'; then
        print_message "✅ Información de símbolos sincronizada"
        symbols_count=$(echo "$response" | jq -r '.data.symbols_count // "N/A"')
        print_message "   Símbolos procesados: $symbols_count"
    else
        print_error "❌ Error sincronizando símbolos"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    fi
}

# Función para sincronizar operaciones recientes
sync_trades() {
    print_section "Sincronización de Operaciones"
    
    print_message "Sincronizando operaciones recientes..."
    
    response=$(curl -s -X POST "http://localhost:8000/api/v1/binance/sync/trades")
    
    if echo "$response" | grep -q '"status":"success"'; then
        print_message "✅ Operaciones sincronizadas"
        trades_count=$(echo "$response" | jq -r '.data.trades_inserted // "N/A"')
        symbol=$(echo "$response" | jq -r '.data.symbol // "N/A"')
        print_message "   Operaciones insertadas: $trades_count"
        print_message "   Símbolo: $symbol"
    else
        print_error "❌ Error sincronizando operaciones"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    fi
}

# Función para sincronizar datos de velas
sync_klines() {
    print_section "Sincronización de Datos de Velas"
    
    print_message "Sincronizando datos de velas..."
    
    response=$(curl -s -X POST "http://localhost:8000/api/v1/binance/sync/klines")
    
    if echo "$response" | grep -q '"status":"success"'; then
        print_message "✅ Datos de velas sincronizados"
        klines_count=$(echo "$response" | jq -r '.data.klines_inserted // "N/A"')
        symbol=$(echo "$response" | jq -r '.data.symbol // "N/A"')
        interval=$(echo "$response" | jq -r '.data.interval // "N/A"')
        print_message "   Velas insertadas: $klines_count"
        print_message "   Símbolo: $symbol"
        print_message "   Intervalo: $interval"
    else
        print_error "❌ Error sincronizando datos de velas"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    fi
}

# Función para sincronizar métricas de rendimiento
sync_performance() {
    print_section "Sincronización de Métricas de Rendimiento"
    
    print_message "Sincronizando métricas de rendimiento..."
    
    response=$(curl -s -X POST "http://localhost:8000/api/v1/binance/sync/performance")
    
    if echo "$response" | grep -q '"status":"success"'; then
        print_message "✅ Métricas de rendimiento sincronizadas"
        total_trades=$(echo "$response" | jq -r '.data.total_trades // "N/A"')
        win_rate=$(echo "$response" | jq -r '.data.win_rate // "N/A"')
        total_profit=$(echo "$response" | jq -r '.data.total_profit // "N/A"')
        portfolio_value=$(echo "$response" | jq -r '.data.portfolio_value_usdt // "N/A"')
        print_message "   Total operaciones: $total_trades"
        print_message "   Tasa de éxito: ${win_rate}%"
        print_message "   Beneficio total: $total_profit"
        print_message "   Valor del portfolio: $portfolio_value USDT"
    else
        print_error "❌ Error sincronizando métricas de rendimiento"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    fi
}

# Función para sincronización completa
sync_full() {
    print_section "Sincronización Completa"
    
    print_message "Iniciando sincronización completa..."
    
    response=$(curl -s -X POST "http://localhost:8000/api/v1/binance/sync/full")
    
    if echo "$response" | grep -q '"status":"success"'; then
        print_message "✅ Sincronización completa finalizada"
        echo "$response" | jq '.data' 2>/dev/null || echo "$response"
    else
        print_error "❌ Error en sincronización completa"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    fi
}

# Función para mostrar datos sincronizados
show_synced_data() {
    print_section "Datos Sincronizados"
    
    print_message "Mostrando datos sincronizados..."
    
    # Información de cuenta
    print_message "📊 Información de cuenta:"
    account_response=$(curl -s -X GET "http://localhost:8000/api/v1/binance/data/account")
    if echo "$account_response" | grep -q '"status":"success"'; then
        echo "$account_response" | jq '.data.account_info' 2>/dev/null || echo "$account_response"
    fi
    
    echo ""
    
    # Balances
    print_message "💰 Balances:"
    balances_response=$(curl -s -X GET "http://localhost:8000/api/v1/binance/data/balances")
    if echo "$balances_response" | grep -q '"status":"success"'; then
        count=$(echo "$balances_response" | jq -r '.data.count // "0"')
        print_message "   Total de activos: $count"
        echo "$balances_response" | jq '.data.balances[0:5]' 2>/dev/null || echo "$balances_response"
    fi
    
    echo ""
    
    # Operaciones recientes
    print_message "📈 Operaciones recientes:"
    trades_response=$(curl -s -X GET "http://localhost:8000/api/v1/binance/data/trades")
    if echo "$trades_response" | grep -q '"status":"success"'; then
        count=$(echo "$trades_response" | jq -r '.data.count // "0"')
        print_message "   Total de operaciones: $count"
        echo "$trades_response" | jq '.data.trades[0:3]' 2>/dev/null || echo "$trades_response"
    fi
    
    echo ""
    
    # Métricas de rendimiento
    print_message "📊 Métricas de rendimiento:"
    performance_response=$(curl -s -X GET "http://localhost:8000/api/v1/binance/data/performance")
    if echo "$performance_response" | grep -q '"status":"success"'; then
        echo "$performance_response" | jq '.data.performance' 2>/dev/null || echo "$performance_response"
    fi
}

# Función para mostrar menú
show_menu() {
    echo ""
    print_section "Menú de Opciones"
    echo "1. 🔍 Verificar credenciales"
    echo "2. 🔗 Probar conexión con Binance"
    echo "3. 👤 Sincronizar información de cuenta"
    echo "4. 💰 Sincronizar balances"
    echo "5. 📊 Sincronizar símbolos"
    echo "6. 📈 Sincronizar operaciones"
    echo "7. 📉 Sincronizar datos de velas"
    echo "8. 📊 Sincronizar métricas de rendimiento"
    echo "9. 🔄 Sincronización completa"
    echo "10. 📋 Mostrar datos sincronizados"
    echo "11. 🚀 Ejecutar todo automáticamente"
    echo "0. ❌ Salir"
    echo ""
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
    
    # Verificar credenciales
    check_binance_credentials
    
    # Menú interactivo
    while true; do
        show_menu
        read -p "Selecciona una opción: " choice
        
        case $choice in
            1)
                check_binance_credentials
                ;;
            2)
                test_binance_connection
                ;;
            3)
                sync_account_info
                ;;
            4)
                sync_balances
                ;;
            5)
                sync_symbols
                ;;
            6)
                sync_trades
                ;;
            7)
                sync_klines
                ;;
            8)
                sync_performance
                ;;
            9)
                sync_full
                ;;
            10)
                show_synced_data
                ;;
            11)
                print_message "Ejecutando sincronización automática completa..."
                test_binance_connection && \
                sync_account_info && \
                sync_balances && \
                sync_symbols && \
                sync_trades && \
                sync_klines && \
                sync_performance && \
                show_synced_data
                print_message "✅ Sincronización automática completada"
                ;;
            0)
                print_message "¡Hasta luego!"
                exit 0
                ;;
            *)
                print_error "Opción inválida"
                ;;
        esac
        
        echo ""
        read -p "Presiona Enter para continuar..."
    done
}

# Ejecutar función principal
main "$@" 