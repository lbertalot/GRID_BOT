#!/usr/bin/env bash
# ============================================================================
# GridBot v2.5 — Script de verificación operativa en producción
# Ejecutar manualmente o como cron: bash scripts/verify_production.sh
# ============================================================================

set -euo pipefail

# --- Configuración -----------------------------------------------------------
APP_URL="${APP_URL:-https://YOUR-APP-NAME.herokuapp.com}"
HEROKU_APP="${HEROKU_APP:-YOUR-APP-NAME}"
TIMEOUT=20           # segundos por petición
PASS=0
FAIL=0

green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

check() {
    local label="$1" url="$2" expected_key="${3:-status}"
    printf "  %-42s " "$label"
    body=$(curl -sf --max-time "$TIMEOUT" "$url" 2>&1) && {
        if echo "$body" | grep -q "$expected_key"; then
            green "OK"
            PASS=$((PASS + 1))
        else
            yellow "WARN (responded but missing '$expected_key')"
            FAIL=$((FAIL + 1))
        fi
    } || {
        red "FAIL (no response within ${TIMEOUT}s)"
        FAIL=$((FAIL + 1))
    }
}

check_heroku_var() {
    local var="$1" expected="$2"
    printf "  %-42s " "heroku config $var=$expected"
    val=$(heroku config:get "$var" -a "$HEROKU_APP" 2>/dev/null || echo "__MISSING__")
    if [ "$val" = "$expected" ]; then
        green "OK ($val)"
        PASS=$((PASS + 1))
    elif [ "$val" = "__MISSING__" ]; then
        red "FAIL (variable not set)"
        FAIL=$((FAIL + 1))
    else
        yellow "WARN (actual=$val, expected=$expected)"
        FAIL=$((FAIL + 1))
    fi
}

# --- Ejecución ---------------------------------------------------------------
echo ""
echo "========================================="
echo "  GridBot v2.5 — Verificación operativa"
echo "  $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "  App: $APP_URL"
echo "========================================="
echo ""

echo "1. Endpoints HTTP"
echo "   ---------------"
check "GET /ping"                        "$APP_URL/ping"                   "pong"
check "GET /health"                      "$APP_URL/health"                 "ok"
check "GET /metrics (Prometheus)"        "$APP_URL/metrics"                "gridbot"
check "GET /breakers/summary"            "$APP_URL/breakers/summary"       "breakers"
check "GET /api/reconciliation/summary"  "$APP_URL/api/reconciliation/summary"  "status"
echo ""

echo "2. Variables Heroku críticas"
echo "   -------------------------"
check_heroku_var "TRADING_ENABLED"  "true"
check_heroku_var "EMERGENCY_STOP"   "false"
check_heroku_var "PAPER_TRADING"    "false"
check_heroku_var "ML_ENABLED"       "true"
echo ""

echo "3. Resumen de métricas ML (si disponible)"
echo "   ---------------------------------------"
printf "  %-42s " "ml_regime_used_in_cycle_total"
ml_used=$(curl -sf --max-time "$TIMEOUT" "$APP_URL/metrics" 2>/dev/null | grep -c "gridbot_ml_regime_used_in_cycle_total" || echo 0)
if [ "$ml_used" -gt 0 ]; then
    green "OK (métrica presente)"
    PASS=$((PASS + 1))
else
    yellow "WARN (métrica no encontrada; el ML podría estar desactivado o recién arrancado)"
    FAIL=$((FAIL + 1))
fi

printf "  %-42s " "ml_regime_fallback_total"
ml_fb=$(curl -sf --max-time "$TIMEOUT" "$APP_URL/metrics" 2>/dev/null | grep -c "gridbot_ml_regime_fallback_total" || echo 0)
if [ "$ml_fb" -gt 0 ]; then
    green "OK (métrica presente)"
    PASS=$((PASS + 1))
else
    yellow "WARN (métrica no encontrada; puede no haber ejecutado ciclos aún)"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "========================================="
echo "  Resultado: $PASS OK, $FAIL WARN/FAIL"
echo "========================================="
echo ""

if [ "$FAIL" -gt 0 ]; then
    yellow "Hay ítems que requieren atención. Revisa logs: heroku logs --tail -a $HEROKU_APP"
    exit 1
fi

green "Todo OK."
exit 0
