# 🔍 GridBot v2.5 - Guía de Validación en Producción

> **Objetivo**: Validar que los fixes de Bugs #1, #2 y #3 funcionan correctamente en producción antes de continuar con Bug #4.  
> **Duración**: 24-48 horas de monitoreo  
> **Responsable**: DevOps + Backend Lead

---

## 📋 **CHECKLIST DE VALIDACIÓN**

### Fase 1: Verificación Inmediata (0-2 horas)

- [ ] **Sistema iniciado correctamente**
  ```bash
  docker-compose ps
  # Todos los servicios deben estar "Up" y "healthy"
  ```

- [ ] **Health checks pasando**
  ```bash
  curl http://localhost:8000/health
  # Debe retornar: {"status": "ok", ...}
  ```

- [ ] **Métricas siendo recolectadas**
  ```bash
  curl http://localhost:8000/metrics | head -20
  # Debe mostrar métricas de Prometheus
  ```

- [ ] **Logs sin errores críticos**
  ```bash
  docker logs gridbot_api --tail 100 | grep -i "error\|critical"
  docker logs gridbot_celery_worker --tail 100 | grep -i "error\|critical"
  ```

- [ ] **Redis conectado y operativo**
  ```bash
  docker exec gridbot_redis redis-cli ping
  # Debe retornar: PONG
  ```

- [ ] **PostgreSQL conectado y balances migraron**
  ```bash
  docker exec gridbot_db psql -U griduser -d gridbot -c "\d balances"
  # Debe mostrar tabla con columna 'version'
  ```

---

### Fase 2: Validación Funcional (2-6 horas)

#### ✅ **Bug #1: Optimistic Locking**

**Test 1: Verificar columna version existe**
```bash
docker exec gridbot_db psql -U griduser -d gridbot -c "
  SELECT column_name, data_type 
  FROM information_schema.columns 
  WHERE table_name = 'balances' AND column_name = 'version';
"
# Debe mostrar: version | integer
```

**Test 2: Verificar que versiones incrementan**
```bash
# Antes de un trade
docker exec gridbot_db psql -U griduser -d gridbot -c "
  SELECT asset, amount, version FROM balances WHERE asset = 'USDT';
"
# Anota la versión

# Ejecutar un trade (manualmente o esperar ciclo automático)

# Después del trade
docker exec gridbot_db psql -U griduser -d gridbot -c "
  SELECT asset, amount, version FROM balances WHERE asset = 'USDT';
"
# La versión debe haber incrementado
```

**Test 3: Verificar métrica de conflictos**
```bash
curl -s http://localhost:8000/metrics | grep balance_update_conflicts_total
# Debe existir la métrica (valor inicial puede ser 0)
```

**Criterio de Éxito**:
- ✅ Columna `version` existe en tabla `balances`
- ✅ Versión incrementa con cada actualización
- ✅ Métrica `balance_update_conflicts_total` existe
- ✅ Si hay conflictos (bajo alta carga), todos se resuelven exitosamente

---

#### ✅ **Bug #2: Lock Distribuido**

**Test 1: Verificar que locks se registran en Redis**
```bash
# Durante ejecución de trading_cycle_tick
docker exec gridbot_redis redis-cli KEYS "lock:*"
# Debe mostrar locks activos como: lock:celery:trading_cycle
```

**Test 2: Verificar logs de locks**
```bash
docker logs gridbot_celery_worker --tail 200 | grep -i "lock"
# Debe mostrar mensajes como:
# "🔓 Lock 'trading_cycle' adquirido"
# "✅ Lock 'trading_cycle' liberado"
# Opcional: "🔒 Lock 'trading_cycle' ya está tomado" (si hubo overlap)
```

**Test 3: Verificar métricas de locks**
```bash
curl -s http://localhost:8000/metrics | grep distributed_lock
# Debe mostrar:
# distributed_lock_acquired_total{lock_name="trading_cycle"} N
# distributed_lock_skipped_total{lock_name="trading_cycle"} 0 o bajo
# distributed_lock_duration_seconds{...}
```

**Test 4: Forzar escenario de overlap (opcional)**
```bash
# Reducir timeout de lock temporalmente para testing
# O ejecutar task manualmente mientras otra está corriendo
docker exec gridbot_celery_worker celery -A app.core.celery_app call app.services.trading_tasks.trading_cycle_tick

# Ver logs para confirmar que segunda ejecución se omitió
docker logs gridbot_celery_worker --tail 50 | grep "Lock.*tomado\|skipped"
```

**Criterio de Éxito**:
- ✅ Locks se registran en Redis
- ✅ Logs muestran adquisición y liberación de locks
- ✅ Métricas `distributed_lock_*` existen y incrementan
- ✅ Si hay overlap, segunda ejecución se omite (status: skipped)
- ✅ Tasa de locks omitidos < 5% (normal: 0-2%)

---

#### ✅ **Bug #3: Async I/O**

**Test 1: Latencia de endpoint /health**
```bash
# Ejecutar 10 requests y medir tiempo
time (for i in {1..10}; do curl -s http://localhost:8000/health > /dev/null; done)

# Debe completar en < 2 segundos (promedio <200ms por request)
```

**Test 2: Requests concurrentes no se bloquean**
```bash
# Ejecutar 3 requests en paralelo
(time curl -s http://localhost:8000/health &
 time curl -s http://localhost:8000/health &
 time curl -s http://localhost:8000/health &
 wait)

# Tiempo total debe ser similar a 1 request (no 3x)
```

**Test 3: Verificar logs sin "slow callback"**
```bash
docker logs gridbot_api --tail 200 | grep -i "slow callback\|blocking"
# No debe haber warnings de "slow callback took"
```

**Test 4: Throughput sostenido**
```bash
# Instalar Apache Bench si no existe
# apt-get install apache2-utils

# O usar wrk (más moderno)
# Ejecutar 100 requests con 10 concurrentes
ab -n 100 -c 10 http://localhost:8000/health

# O con curl en loop
for i in {1..20}; do
  (curl -s -o /dev/null -w "%{time_total}\n" http://localhost:8000/health &)
done | awk '{sum+=$1; count++} END {print "Promedio:", sum/count "s"}'

# Latencia promedio debe ser < 100ms
```

**Criterio de Éxito**:
- ✅ Latencia promedio < 50ms
- ✅ Requests concurrentes no se bloquean (ratio < 3x)
- ✅ Sin warnings de "slow callback"
- ✅ Throughput > 30 req/s

---

### Fase 3: Monitoreo Continuo (6-48 horas)

#### 📊 **Queries Prometheus**

**1. Tasa de conflictos de balance**
```promql
# Debe ser 0 o muy bajo (< 1% de updates)
rate(balance_update_conflicts_total[5m])

# Por asset
sum(rate(balance_update_conflicts_total[5m])) by (asset)
```

**2. Tasa de locks adquiridos vs omitidos**
```promql
# Locks adquiridos (debe incrementar cada 60s para trading_cycle)
rate(distributed_lock_acquired_total{lock_name="trading_cycle"}[5m])

# Locks omitidos (debe ser 0 o muy bajo)
rate(distributed_lock_skipped_total{lock_name="trading_cycle"}[5m])

# Porcentaje de locks omitidos (debe ser < 5%)
(
  rate(distributed_lock_skipped_total[5m]) / 
  (rate(distributed_lock_acquired_total[5m]) + rate(distributed_lock_skipped_total[5m]))
) * 100
```

**3. Duración de locks (debe ser < timeout)**
```promql
# P95 de duración de locks
histogram_quantile(0.95, 
  rate(distributed_lock_duration_seconds_bucket[5m])
)

# Por lock name
histogram_quantile(0.95, 
  rate(distributed_lock_duration_seconds_bucket{lock_name="trading_cycle"}[5m])
)
```

**4. Latencia de API**
```promql
# P50 latency (debe ser < 50ms)
histogram_quantile(0.50, 
  rate(api_request_duration_seconds_bucket[5m])
)

# P99 latency (debe ser < 250ms)
histogram_quantile(0.99, 
  rate(api_request_duration_seconds_bucket[5m])
)
```

**5. Throughput de API**
```promql
# Requests por segundo
rate(api_requests_total[5m])

# Por endpoint
sum(rate(api_requests_total[5m])) by (endpoint)
```

---

#### 📈 **Dashboard Grafana**

**Panel 1: Balance Conflicts**
```
Título: "Balance Update Conflicts"
Query: sum(rate(balance_update_conflicts_total[5m])) by (asset)
Tipo: Time series
Alerta: > 10 conflicts/min
```

**Panel 2: Distributed Locks**
```
Título: "Lock Acquisition Rate"
Query: rate(distributed_lock_acquired_total[5m])
Tipo: Time series
```

```
Título: "Lock Skip Rate (%)"
Query: (rate(distributed_lock_skipped_total[5m]) / (rate(distributed_lock_acquired_total[5m]) + rate(distributed_lock_skipped_total[5m]))) * 100
Tipo: Gauge
Alerta: > 5%
```

**Panel 3: API Performance**
```
Título: "API Latency (P50/P95/P99)"
Queries:
- P50: histogram_quantile(0.50, rate(api_request_duration_seconds_bucket[5m]))
- P95: histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))
- P99: histogram_quantile(0.99, rate(api_request_duration_seconds_bucket[5m]))
Tipo: Time series
```

---

#### 🔔 **Alertas Recomendadas**

**Alerta 1: High Balance Conflicts**
```yaml
- alert: HighBalanceConflicts
  expr: rate(balance_update_conflicts_total[5m]) > 1
  for: 10m
  annotations:
    summary: "Alta tasa de conflictos de balance (>1/min)"
    description: "Asset {{ $labels.asset }} tiene {{ $value }} conflictos/min"
```

**Alerta 2: High Lock Skip Rate**
```yaml
- alert: HighLockSkipRate
  expr: |
    (
      rate(distributed_lock_skipped_total[5m]) / 
      (rate(distributed_lock_acquired_total[5m]) + rate(distributed_lock_skipped_total[5m]))
    ) > 0.10
  for: 15m
  annotations:
    summary: "Tasa alta de locks omitidos (>10%)"
    description: "Lock {{ $labels.lock_name }} tiene {{ $value }}% de omisiones"
```

**Alerta 3: High API Latency**
```yaml
- alert: HighAPILatency
  expr: histogram_quantile(0.99, rate(api_request_duration_seconds_bucket[5m])) > 0.5
  for: 5m
  annotations:
    summary: "Latencia alta de API (P99 >500ms)"
    description: "P99 latency: {{ $value }}s"
```

**Alerta 4: Lock Stuck**
```yaml
- alert: LockStuckInRedis
  expr: |
    (time() - redis_key_ttl{key=~"lock:.*"}) > 600
  for: 5m
  annotations:
    summary: "Lock atascado en Redis (>10min)"
    description: "Lock {{ $labels.key }} lleva >10min activo"
```

---

### Fase 4: Validación de Integridad Financiera (24-48 horas)

#### 💰 **Reconciliación de Balances**

**Test 1: Balance interno vs Binance (endpoint)**
```bash
curl -s http://localhost:8000/api/reconciliation/summary | jq .
# Verificar que 'portfolio_total_usdt' sea razonable
```

**Test 2: Ejecutar reconciliación manual**
```bash
# Desde dentro del contenedor
docker exec gridbot_api python -c "
from app.services.reconciliation_service import ReconciliationService
from app.services.binance_client_singleton import get_binance_client_singleton
import asyncio

async def check():
    client = get_binance_client_singleton()
    recon = ReconciliationService(client.client, None)
    result = await recon.run_reconciliation_cycle()
    print(f'Discrepancia: {result.get(\"discrepancy_pct\", 0):.2f}%')
    
asyncio.run(check())
"

# Discrepancia debe ser < 1%
```

**Test 3: Verificar trades en BD**
```bash
docker exec gridbot_db psql -U griduser -d gridbot -c "
  SELECT 
    COUNT(*) as total_trades,
    COUNT(DISTINCT symbol) as unique_symbols,
    SUM(CASE WHEN side = 'BUY' THEN 1 ELSE 0 END) as buys,
    SUM(CASE WHEN side = 'SELL' THEN 1 ELSE 0 END) as sells
  FROM trades
  WHERE timestamp > NOW() - INTERVAL '24 hours';
"
```

**Test 4: Verificar que no hay pérdida de fondos**
```bash
# Comparar balance inicial vs actual
docker exec gridbot_db psql -U griduser -d gridbot -c "
  SELECT 
    asset,
    amount,
    version,
    updated_at
  FROM balances
  WHERE asset IN ('USDT', 'BTC', 'ETH')
  ORDER BY updated_at DESC;
"

# Verificar con Binance
curl -s http://localhost:8000/api/reconciliation/summary | jq '.portfolio_total_usdt'

# Comparar ambos valores (diferencia < 1%)
```

**Criterio de Éxito**:
- ✅ Discrepancia balance interno vs Binance < 1%
- ✅ Todos los trades registrados en BD
- ✅ Versiones de balances incrementan correctamente
- ✅ No hay pérdidas inexplicables de fondos

---

## 📊 **REPORTE DE VALIDACIÓN**

### Template de Reporte Diario

```markdown
# GridBot v2.5 - Reporte de Validación
**Fecha**: [YYYY-MM-DD]
**Periodo**: [HH:MM] - [HH:MM]

## Estado General
- [ ] Sistema operativo sin interrupciones
- [ ] Logs sin errores críticos
- [ ] Métricas siendo recolectadas

## Bug #1: Optimistic Locking
- Conflictos detectados: [N]
- Conflictos resueltos: [N]
- Tasa de conflictos: [N/min]
- ✅/❌ Criterio: < 1 conflicto/min

## Bug #2: Lock Distribuido
- Locks adquiridos: [N]
- Locks omitidos: [N]
- Tasa de omisión: [N%]
- ✅/❌ Criterio: < 5% omitidos

## Bug #3: Async I/O
- Latencia P50: [N ms]
- Latencia P99: [N ms]
- Throughput: [N req/s]
- ✅/❌ Criterio: P99 < 250ms, throughput > 30 req/s

## Integridad Financiera
- Discrepancia balance: [N%]
- Trades ejecutados: [N]
- ✅/❌ Criterio: Discrepancia < 1%

## Incidentes
- [Ninguno] / [Descripción de incidentes]

## Recomendaciones
- [Acciones sugeridas]

## Conclusión
- ✅ Sistema validado, continuar con Bug #4
- ⚠️ Requiere ajustes menores
- ❌ Requiere correcciones críticas
```

---

## 🚨 **ESCENARIOS DE PROBLEMAS Y SOLUCIONES**

### Problema 1: Alta tasa de conflictos de balance (>5%)

**Síntomas**:
```bash
curl -s http://localhost:8000/metrics | grep balance_update_conflicts_total
# balance_update_conflicts_total{asset="USDT"} 50
```

**Diagnóstico**:
```bash
# Ver logs de conflictos
docker logs gridbot_api | grep "Conflicto de concurrencia"

# Ver qué está causando alta concurrencia
docker exec gridbot_db psql -U griduser -d gridbot -c "
  SELECT asset, version, updated_at 
  FROM balances 
  WHERE asset = 'USDT' 
  ORDER BY updated_at DESC LIMIT 10;
"
```

**Solución**:
- Aumentar `max_retries` en `BalanceService` (de 10 a 20)
- Revisar si hay múltiples procesos actualizando el mismo balance
- Considerar reducir frecuencia de actualizaciones

---

### Problema 2: Locks atascados en Redis

**Síntomas**:
```bash
docker exec gridbot_redis redis-cli KEYS "lock:*"
# Muestra locks que llevan >10min
```

**Diagnóstico**:
```bash
# Ver TTL de locks
docker exec gridbot_redis redis-cli TTL "lock:celery:trading_cycle"
# Si es -1, el lock no tiene TTL (problema!)
```

**Solución**:
```bash
# Liberar lock manualmente
docker exec gridbot_redis redis-cli DEL "lock:celery:trading_cycle"

# Reiniciar Celery workers
docker-compose restart celery_worker celery_beat

# Verificar logs
docker logs gridbot_celery_worker --tail 50
```

---

### Problema 3: Alta latencia de API (P99 >500ms)

**Síntomas**:
```bash
# Latencia alta en Prometheus
curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,%20rate(api_request_duration_seconds_bucket[5m]))" | jq .
```

**Diagnóstico**:
```bash
# Ver logs de uvicorn
docker logs gridbot_api | grep "slow callback"

# Ver qué endpoints son lentos
docker logs gridbot_api | grep "ms" | sort -k2 -n | tail -20
```

**Solución**:
- Verificar que todas las llamadas sync usan `asyncio.to_thread()`
- Revisar conexiones a Binance (puede estar lenta)
- Considerar aumentar workers de uvicorn
- Revisar queries a PostgreSQL

---

### Problema 4: Discrepancia balance >5%

**Síntomas**:
```bash
curl -s http://localhost:8000/api/reconciliation/summary | jq '.portfolio_total_usdt'
# Valor muy diferente a esperado
```

**Diagnóstico**:
```bash
# Ejecutar script de auditoría
cd /Users/leandrobertalot/Documents/grid_bot
python scripts/forensic_audit.py

# Ver trades recientes
docker exec gridbot_db psql -U griduser -d gridbot -c "
  SELECT * FROM trades 
  ORDER BY timestamp DESC 
  LIMIT 20;
"

# Comparar con Binance
# (manual desde web de Binance)
```

**Solución**:
- Ejecutar reconciliación forzada
- Verificar que trades se están registrando correctamente
- Revisar logs de TradeExecutor
- Si persiste, considerar rollback y investigar

---

## ✅ **CRITERIOS DE APROBACIÓN PARA BUG #4**

Para continuar con Bug #4, el sistema debe cumplir:

### Requisitos Mínimos (MUST)
- [ ] ✅ **0 errores críticos** en logs durante 24h
- [ ] ✅ **Discrepancia balance < 1%** en las últimas 24h
- [ ] ✅ **Tasa de conflictos < 1/min** promedio
- [ ] ✅ **Tasa de locks omitidos < 5%** promedio
- [ ] ✅ **Latencia P99 < 250ms** promedio
- [ ] ✅ **Throughput > 30 req/s** sostenido

### Requisitos Deseables (SHOULD)
- [ ] ✅ **0 conflictos de balance** en 24h
- [ ] ✅ **0 locks omitidos** en 24h (ciclos completan en <60s)
- [ ] ✅ **Latencia P99 < 100ms**
- [ ] ✅ **Throughput > 50 req/s**

### Requisitos Opcionales (NICE TO HAVE)
- [ ] ✅ Dashboard Grafana funcional con todos los panels
- [ ] ✅ Alertas configuradas y testeadas
- [ ] ✅ Documentación actualizada con findings

---

## 🎯 **SIGUIENTE PASO DESPUÉS DE VALIDACIÓN**

Una vez completada la validación exitosamente:

1. **Generar Reporte Final**
   ```markdown
   # Validación Completada ✅
   - Periodo: [fecha inicio] - [fecha fin]
   - Duración: [horas] de monitoreo
   - Resultado: APROBADO
   
   ## Métricas Clave
   - Conflictos: [N] (< 1/min ✅)
   - Locks omitidos: [N%] (< 5% ✅)
   - Latencia P99: [N ms] (< 250ms ✅)
   - Discrepancia: [N%] (< 1% ✅)
   
   ## Conclusión
   Sistema estable y listo para Bug #4
   ```

2. **Commit de Estado Estable**
   ```bash
   git add .
   git commit -m "chore: bugs #1-3 validated in production

   - Bug #1: Optimistic locking working (0 conflicts in 24h)
   - Bug #2: Distributed locks working (0 overlaps in 24h)
   - Bug #3: Async I/O working (P99 latency <100ms)
   
   Metrics:
   - Throughput: 49 req/s
   - Latency P99: 50ms
   - Balance discrepancy: <0.1%
   
   Ready for Bug #4: WebSocket order fills"
   ```

3. **Iniciar Bug #4**
   - Revisar `BUGFIX_IMPLEMENTATION_GUIDE.md` sección Bug #4
   - Estimar tiempo con equipo
   - Iniciar implementación

---

## 📞 **CONTACTOS DE SOPORTE**

En caso de problemas durante validación:

1. **DevOps Lead**: [contacto]
2. **Backend Lead**: [contacto]
3. **On-Call**: [contacto]

### Telegram Alerts
- Token: `TELEGRAM_BOT_TOKEN` en `.env`
- Chat ID: `TELEGRAM_CHAT_ID` en `.env`

---

## 📚 **REFERENCIAS**

- [BUG1_COMPLETION_REPORT.md](./BUG1_COMPLETION_REPORT.md)
- [BUG2_COMPLETION_REPORT.md](./BUG2_COMPLETION_REPORT.md)
- [BUG3_COMPLETION_REPORT.md](./BUG3_COMPLETION_REPORT.md)
- [EXECUTIVE_SUMMARY_PROGRESS.md](./EXECUTIVE_SUMMARY_PROGRESS.md)
- [PRODUCTION_LAUNCH_GUIDE.md](./PRODUCTION_LAUNCH_GUIDE.md)

---

**Preparado por**: Cursor AI Agent  
**Fecha**: 2026-01-03  
**Versión**: 1.0  
**Próxima Revisión**: Después de validación 24-48h

---


