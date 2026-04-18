#!/bin/bash
# GridBot — Verificar que el proxy Squid funciona correctamente
# Uso: ./verify_proxy.sh <IP_VM> <USUARIO> <PASSWORD>
#
# Ejemplo: ./verify_proxy.sh 123.45.67.89 gridbot miPassword123

set -euo pipefail

IP="${1:-}"
USER="${2:-gridbot}"
PASS="${3:-}"

if [[ -z "$IP" || -z "$PASS" ]]; then
    echo "Uso: $0 <IP_VM> <USUARIO> <PASSWORD>"
    echo "Ejemplo: $0 123.45.67.89 gridbot miPassword123"
    exit 1
fi

PROXY_URL="http://${USER}:${PASS}@${IP}:3128"
PASS_DISPLAY="OK"
echo ""
echo "============================================"
echo " Verificación del proxy GridBot"
echo "============================================"
echo " Proxy: http://${USER}:***@${IP}:3128"
echo ""

# Test 1: Conectividad al proxy
echo -n "[1/4] Conectividad al puerto 3128... "
if nc -z -w5 "$IP" 3128 2>/dev/null; then
    echo "OK"
else
    echo "FALLO — el puerto 3128 no responde."
    echo "      Verifica: security list de Oracle Cloud y firewall de la VM."
    exit 1
fi

# Test 2: Ping a Binance via proxy
echo -n "[2/4] Binance /api/v3/ping via proxy... "
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --proxy "$PROXY_URL" \
    --connect-timeout 10 --max-time 15 \
    "https://api.binance.com/api/v3/ping" 2>/dev/null || echo "000")

if [[ "$RESPONSE" == "200" ]]; then
    echo "OK (HTTP 200)"
else
    echo "FALLO (HTTP $RESPONSE)"
    echo "      Verifica las credenciales y la config de Squid."
    exit 1
fi

# Test 3: Server time via proxy
echo -n "[3/4] Binance /api/v3/time via proxy... "
TIME_RESP=$(curl -s --proxy "$PROXY_URL" \
    --connect-timeout 10 --max-time 15 \
    "https://api.binance.com/api/v3/time" 2>/dev/null)

if echo "$TIME_RESP" | grep -q "serverTime"; then
    echo "OK ($TIME_RESP)"
else
    echo "FALLO — respuesta: $TIME_RESP"
    exit 1
fi

# Test 4: Verificar que NO permite otros dominios
echo -n "[4/4] Bloqueo de dominios no-Binance... "
BLOCKED=$(curl -s -o /dev/null -w "%{http_code}" --proxy "$PROXY_URL" \
    --connect-timeout 10 --max-time 15 \
    "https://httpbin.org/ip" 2>/dev/null || echo "000")

if [[ "$BLOCKED" == "403" || "$BLOCKED" == "000" ]]; then
    echo "OK (bloqueado correctamente, HTTP $BLOCKED)"
else
    echo "ADVERTENCIA — httpbin.org respondió HTTP $BLOCKED (debería estar bloqueado)"
fi

echo ""
echo "============================================"
echo " PROXY VERIFICADO CORRECTAMENTE"
echo "============================================"
echo ""
echo " Próximos pasos:"
echo " 1. En Binance: whitelistea la IP ${IP}"
echo " 2. En Binance: activa 'Habilitar spot y trading de margen'"
echo " 3. En Binance: selecciona 'Restringir IP' con la IP ${IP}"
echo " 4. Ejecuta:"
echo "    heroku config:set BINANCE_PROXY_URL=${PROXY_URL} -a grid-bot-ia-eu"
echo "    heroku restart -a grid-bot-ia-eu"
echo "============================================"
