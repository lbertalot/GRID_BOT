#!/usr/bin/env bash
# Smoke de observabilidad: detecta cAdvisor/Prometheus "healthy pero inútil".
# Paper-safe: solo lecturas HTTP locales. Exit 0 = PASS, 1 = FAIL.
#
# Uso:
#   ./scripts/smoke_observability.sh
#   CADVISOR_URL=http://localhost:8081 PROMETHEUS_URL=http://localhost:9090 ./scripts/smoke_observability.sh
set -euo pipefail

CADVISOR_URL="${CADVISOR_URL:-http://localhost:8081}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
TIMEOUT="${SMOKE_TIMEOUT:-8}"

pass=0
fail=0

_print() {
  printf '[%s] %s\n' "$1" "$2"
}

check() {
  local name="$1"
  shift
  if "$@"; then
    _print PASS "$name"
    pass=$((pass + 1))
    return 0
  fi
  _print FAIL "$name"
  fail=$((fail + 1))
  return 0
}

echo "--- Smoke observability (cadvisor=${CADVISOR_URL} prometheus=${PROMETHEUS_URL}) ---"

# 1) /api/v1.3/docker no vacío (factory Docker activa)
check "cadvisor /api/v1.3/docker no vacío" bash -c "
  body=\$(curl -sf --max-time ${TIMEOUT} '${CADVISOR_URL}/api/v1.3/docker') || exit 1
  python3 -c \"import json,sys; d=json.loads(sys.argv[1]); raise SystemExit(0 if isinstance(d, dict) and len(d) > 0 else 1)\" \"\$body\"
"

# 2) Prometheus target cadvisor up
check "prometheus up{job=cadvisor} == 1" bash -c "
  body=\$(curl -sf --max-time ${TIMEOUT} --get '${PROMETHEUS_URL}/api/v1/query' \
    --data-urlencode 'query=up{job=\"cadvisor\"}') || exit 1
  python3 -c \"
import json,sys
d=json.loads(sys.argv[1])
r=d.get('data',{}).get('result') or []
raise SystemExit(0 if r and str(r[0].get('value',[None,''])[1])=='1' else 1)
\" \"\$body\"
"

# 3) Métricas por contenedor (id != root '/')
check "prometheus container_cpu id!=/ >= 1" bash -c "
  body=\$(curl -sf --max-time ${TIMEOUT} --get '${PROMETHEUS_URL}/api/v1/query' \
    --data-urlencode 'query=count(container_cpu_usage_seconds_total{id!=\"/\"})') || exit 1
  python3 -c \"
import json,sys
d=json.loads(sys.argv[1])
r=d.get('data',{}).get('result') or []
if not r:
    raise SystemExit(1)
raise SystemExit(0 if float(r[0]['value'][1]) >= 1 else 1)
\" \"\$body\"
"

echo
if [[ "$fail" -eq 0 ]]; then
  _print PASS "Observabilidad cadvisor/prometheus verificable (${pass} checks)"
  exit 0
fi
_print FAIL "${fail} check(s) fallaron (${pass} ok). Ver Docs/ops/silent-failures-checklist.md"
exit 1
