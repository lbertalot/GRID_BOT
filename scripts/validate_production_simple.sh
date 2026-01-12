#!/bin/bash
# GridBot v2.5 - Validación Simple en Producción
# Script bash sin dependencias externas

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🔍 GRIDBOT V2.5 - VALIDACIÓN EN PRODUCCIÓN 🔍              ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Contadores
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

# Función para imprimir con formato
print_status() {
    if [ "$1" = "OK" ]; then
        echo -e "${GREEN}✅ $2${NC}"
        ((CHECKS_PASSED++))
    elif [ "$1" = "FAIL" ]; then
        echo -e "${RED}❌ $2${NC}"
        ((CHECKS_FAILED++))
    elif [ "$1" = "WARN" ]; then
        echo -e "${YELLOW}⚠️  $2${NC}"
        ((CHECKS_WARNING++))
    else
        echo -e "${CYAN}ℹ️  $2${NC}"
    fi
}

echo "════════════════════════════════════════════════════════════════════"
echo "  📊 FASE 1: VERIFICACIÓN DE SERVICIOS"
echo "════════════════════════════════════════════════════════════════════"
echo ""

# 1. API Health
echo -n "Verificando API... "
API_HEALTH=$(curl -s http://localhost:8000/health 2>&1)
if echo "$API_HEALTH" | grep -q '"status":"ok"'; then
    print_status "OK" "API: Healthy (http://localhost:8000)"
else
    print_status "FAIL" "API: No responde correctamente"
fi

# 2. Redis
echo -n "Verificando Redis... "
REDIS_STATUS=$(docker exec gridbot_redis redis-cli ping 2>&1)
if echo "$REDIS_STATUS" | grep -q "PONG"; then
    print_status "OK" "Redis: Connected"
else
    print_status "FAIL" "Redis: No responde"
fi

# 3. PostgreSQL
echo -n "Verificando PostgreSQL... "
PG_STATUS=$(docker exec gridbot_db pg_isready -U griduser 2>&1)
if echo "$PG_STATUS" | grep -q "accepting connections"; then
    print_status "OK" "PostgreSQL: Connected"
else
    print_status "FAIL" "PostgreSQL: No responde"
fi

# 4. Celery Worker
echo -n "Verificando Celery Worker... "
CELERY_STATUS=$(docker ps --filter "name=celery_worker" --format "{{.Status}}")
if echo "$CELERY_STATUS" | grep -q "healthy"; then
    print_status "OK" "Celery Worker: Healthy"
elif echo "$CELERY_STATUS" | grep -q "Up"; then
    print_status "WARN" "Celery Worker: Running (sin healthcheck)"
else
    print_status "FAIL" "Celery Worker: No está corriendo"
fi

# 5. Prometheus
echo -n "Verificando Prometheus... "
PROM_STATUS=$(curl -s http://localhost:9090/-/healthy 2>&1)
if [ $? -eq 0 ]; then
    print_status "OK" "Prometheus: Healthy (http://localhost:9090)"
else
    print_status "WARN" "Prometheus: No responde (opcional)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  🐛 FASE 2: VALIDACIÓN DE BUGS"
echo "════════════════════════════════════════════════════════════════════"
echo ""

# Bug #1: Optimistic Locking
echo "🔍 Bug #1: Optimistic Locking"
echo "────────────────────────────────────────────────────────────────────"

# Verificar columna version
echo -n "  Verificando columna 'version' en tabla balances... "
VERSION_COL=$(docker exec gridbot_db psql -U griduser -d gridbot -t -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'balances' AND column_name = 'version';" 2>&1)
if echo "$VERSION_COL" | grep -q "version"; then
    print_status "OK" "  Columna 'version' existe en tabla balances"
else
    print_status "FAIL" "  Columna 'version' NO existe"
fi

# Verificar métrica
echo -n "  Verificando métrica balance_update_conflicts_total... "
BALANCE_METRIC=$(curl -s http://localhost:8000/metrics 2>&1 | grep "balance_update_conflicts_total")
if [ -n "$BALANCE_METRIC" ]; then
    print_status "OK" "  Métrica 'balance_update_conflicts_total' existe"
    CONFLICTS=$(echo "$BALANCE_METRIC" | grep -v "^#" | awk '{sum+=$NF} END {print sum}')
    echo -e "     ${CYAN}Conflictos totales: ${CONFLICTS:-0}${NC}"
else
    print_status "FAIL" "  Métrica NO existe"
fi

# Verificar balances en BD
echo -n "  Verificando balances en BD... "
BALANCES=$(docker exec gridbot_db psql -U griduser -d gridbot -t -c "SELECT COUNT(*) FROM balances WHERE version IS NOT NULL;" 2>&1)
if [ $? -eq 0 ] && [ "$BALANCES" -gt 0 ] 2>/dev/null; then
    print_status "OK" "  Balances con versión: $BALANCES registros"
else
    print_status "WARN" "  No hay balances o tabla vacía (puede ser normal)"
fi

echo ""

# Bug #2: Lock Distribuido
echo "🔍 Bug #2: Lock Distribuido"
echo "────────────────────────────────────────────────────────────────────"

# Verificar métricas de locks
echo -n "  Verificando métricas de distributed_lock... "
LOCK_METRICS=$(curl -s http://localhost:8000/metrics 2>&1 | grep "distributed_lock")
if [ -n "$LOCK_METRICS" ]; then
    print_status "OK" "  Métricas de lock distribuido existen"
    
    ACQUIRED=$(echo "$LOCK_METRICS" | grep "distributed_lock_acquired_total" | grep -v "^#" | awk '{sum+=$NF} END {print sum}')
    SKIPPED=$(echo "$LOCK_METRICS" | grep "distributed_lock_skipped_total" | grep -v "^#" | awk '{sum+=$NF} END {print sum}')
    
    echo -e "     ${CYAN}Locks adquiridos: ${ACQUIRED:-0}${NC}"
    echo -e "     ${CYAN}Locks omitidos: ${SKIPPED:-0}${NC}"
    
    if [ "${ACQUIRED:-0}" -gt 0 ] 2>/dev/null; then
        SKIP_RATE=$(echo "scale=2; ($SKIPPED / $ACQUIRED) * 100" | bc)
        echo -e "     ${CYAN}Tasa de omisión: ${SKIP_RATE}%${NC}"
        
        if [ $(echo "$SKIP_RATE < 5" | bc) -eq 1 ]; then
            print_status "OK" "  Tasa de omisión < 5% (óptimo)"
        else
            print_status "WARN" "  Tasa de omisión > 5% (revisar)"
        fi
    else
        print_status "WARN" "  No hay locks registrados aún (esperar tasks)"
    fi
else
    print_status "FAIL" "  Métricas de lock NO existen"
fi

# Verificar locks activos en Redis
echo -n "  Verificando locks activos en Redis... "
ACTIVE_LOCKS=$(docker exec gridbot_redis redis-cli KEYS "lock:*" 2>&1 | grep -v "empty")
if [ -n "$ACTIVE_LOCKS" ]; then
    LOCK_COUNT=$(echo "$ACTIVE_LOCKS" | wc -l | tr -d ' ')
    print_status "OK" "  $LOCK_COUNT lock(s) activo(s) en Redis"
else
    print_status "WARN" "  No hay locks activos (normal si no hay tasks corriendo)"
fi

echo ""

# Bug #3: Async I/O
echo "🔍 Bug #3: Async I/O"
echo "────────────────────────────────────────────────────────────────────"

# Test de latencia simple
echo -n "  Midiendo latencia de /health (10 requests)... "
TOTAL_TIME=0
for i in {1..10}; do
    START=$(date +%s%N)
    curl -s http://localhost:8000/health > /dev/null 2>&1
    END=$(date +%s%N)
    ELAPSED=$((($END - $START) / 1000000)) # Convertir a ms
    TOTAL_TIME=$(($TOTAL_TIME + $ELAPSED))
done
AVG_LATENCY=$(($TOTAL_TIME / 10))

if [ $AVG_LATENCY -lt 50 ]; then
    print_status "OK" "  Latencia promedio: ${AVG_LATENCY}ms (excelente)"
elif [ $AVG_LATENCY -lt 100 ]; then
    print_status "OK" "  Latencia promedio: ${AVG_LATENCY}ms (bueno)"
else
    print_status "WARN" "  Latencia promedio: ${AVG_LATENCY}ms (revisar)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  📊 RESUMEN DE VALIDACIÓN"
echo "════════════════════════════════════════════════════════════════════"
echo ""

echo -e "${GREEN}✅ Checks pasados:   $CHECKS_PASSED${NC}"
echo -e "${YELLOW}⚠️  Warnings:         $CHECKS_WARNING${NC}"
echo -e "${RED}❌ Checks fallidos:  $CHECKS_FAILED${NC}"
echo ""

# Conclusión
if [ $CHECKS_FAILED -eq 0 ]; then
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                    ║"
    echo "║                    ✅ VALIDACIÓN EXITOSA ✅                         ║"
    echo "║                                                                    ║"
    echo "║  El sistema está funcionando correctamente.                        ║"
    echo "║  Se recomienda monitoreo continuo por 24-48h antes de Bug #4.      ║"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    if [ $CHECKS_WARNING -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Hay $CHECKS_WARNING warnings (revisar arriba)${NC}"
        echo ""
    fi
    
    exit 0
else
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                    ║"
    echo "║                    ❌ VALIDACIÓN FALLIDA ❌                         ║"
    echo "║                                                                    ║"
    echo "║  Hay $CHECKS_FAILED check(s) fallidos que requieren atención.              ║"
    echo "║  Por favor, revisa los detalles arriba.                            ║"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    exit 1
fi

