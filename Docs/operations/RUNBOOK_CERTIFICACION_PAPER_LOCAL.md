# Runbook - Certificacion Paper Local (Checklist Ejecutable)

Objetivo: certificar que `grid_bot` en Docker Compose local opera en modo **paper trading** de forma estable, observable y repetible.

Atajo diario (10 comandos):
- Ver tambien `Docs/operations/RUNBOOK_CERTIFICACION_PAPER_LOCAL_RAPIDO.md`.

Modo de uso:
- Ejecutar cada bloque en orden.
- Marcar `[x]` solo cuando el **criterio de aceptacion** se cumple.
- Registrar evidencia en una carpeta de sesion (logs/salidas).

---

## 0) Metadatos de certificacion

- Fecha/hora inicio:
- Responsable:
- Branch/commit:
- Entorno (OS + Docker version):
- Objetivo de la corrida (smoke / regresion / pre-release):

Crear carpeta de evidencia:

```bash
mkdir -p reports/certificacion_paper/$(date -u +%Y%m%dT%H%M%SZ)
```

---

## 1) Pre-flight (sanidad de entorno)

- [ ] 1.1 Docker y Compose disponibles

```bash
docker --version
docker compose version
```

Criterio de aceptacion:
- Ambos comandos responden sin error.

- [ ] 1.2 Revisar override efectivo de paper en compose

```bash
docker compose -f docker-compose.local.yml config | rg "PAPER_TRADING|FORCE_REAL_MODE|TRADING_ENABLED|BINANCE_TESTNET"
```

Criterio de aceptacion:
- `PAPER_TRADING: "true"`
- `FORCE_REAL_MODE` vacio o `false`
- `TRADING_ENABLED: "true"` (si ese es el comportamiento esperado para paper)

---

## 2) Arranque limpio del stack

- [ ] 2.1 Bajar stack y volúmenes (solo local)

```bash
docker compose -f docker-compose.local.yml down -v --remove-orphans
```

- [ ] 2.2 Levantar stack completo

```bash
docker compose -f docker-compose.local.yml up --build -d
```

- [ ] 2.3 Verificar estado de contenedores

```bash
docker compose -f docker-compose.local.yml ps
```

Criterio de aceptacion:
- `db` y `redis` en `healthy`.
- `migrate` en `exited (0)`.
- `api`, `worker`, `beat`, `flower`, `prometheus`, `grafana` en `running`.

---

## 3) Salud API + observabilidad base

- [ ] 3.1 Healthcheck API

```bash
curl -sf http://localhost:8000/health
```

Criterio de aceptacion:
- HTTP 200 y payload de salud.

- [ ] 3.2 Ejecutar ops watch (ventana 10m)

```bash
python3 scripts/ops_watch/run_once.py
```

Criterio de aceptacion:
- `reports/ops_watch/LATEST.md` en `green` o con hallazgos explicables.

- [ ] 3.3 Verificar endpoints de observabilidad

```bash
curl -sf http://localhost:9090/-/ready
curl -sf http://localhost:8000/metrics >/dev/null
```

Criterio de aceptacion:
- Prometheus listo.
- Endpoint de metricas de API responde.

---

## 4) Certificacion de modo paper

- [ ] 4.1 Verificar variable efectiva dentro de API

```bash
docker compose -f docker-compose.local.yml exec -T api python - <<'PY'
import os
print("PAPER_TRADING=", os.getenv("PAPER_TRADING"))
print("FORCE_REAL_MODE=", os.getenv("FORCE_REAL_MODE"))
print("TRADING_ENABLED=", os.getenv("TRADING_ENABLED"))
PY
```

Criterio de aceptacion:
- `PAPER_TRADING=true`.
- `FORCE_REAL_MODE` no habilita real.

- [ ] 4.2 Simulacion de orden (dry-run)

```bash
make dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET
```

Criterio de aceptacion:
- Validacion de orden correcta.
- No evidencia de envio real a exchange.

---

## 5) Certificacion de datos en DB

- [ ] 5.1 Verificar conectividad SQL

```bash
docker compose -f docker-compose.local.yml exec -T db psql -U griduser -d gridbot -c "select now();"
```

- [ ] 5.2 Conteos base (tablas operativas)

```bash
docker compose -f docker-compose.local.yml exec -T db psql -U griduser -d gridbot -c "
SELECT
  (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='trades') as has_trades_table,
  (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='portfolio_snapshots') as has_portfolio_snapshots_table,
  (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='performance_metrics') as has_performance_metrics_table;
"
```

- [ ] 5.3 Medir datos reales capturados

```bash
docker compose -f docker-compose.local.yml exec -T db psql -U griduser -d gridbot -c "
SELECT
  (SELECT count(*) FROM trades) as trades_count,
  (SELECT count(*) FROM portfolio_snapshots) as snapshots_count,
  (SELECT max(captured_at) FROM portfolio_snapshots) as last_snapshot_at;
"
```

Criterio de aceptacion:
- Tablas existen.
- Hay datos o, si no hay datos, queda identificado el motivo (tiempo insuficiente, tarea no ejecutada, dependencia externa).

---

## 6) Certificacion Celery (worker/beat)

- [ ] 6.1 Worker responde a inspect ping

```bash
docker compose -f docker-compose.local.yml exec -T worker celery -A app.core.celery_app inspect ping --timeout=10
```

- [ ] 6.2 Confirmar tareas registradas

```bash
docker compose -f docker-compose.local.yml exec -T worker celery -A app.core.celery_app inspect registered --timeout=10
```

- [ ] 6.3 Confirmar scheduler activo

```bash
docker compose -f docker-compose.local.yml logs --since 10m beat
```

Criterio de aceptacion:
- Worker responde.
- Tareas clave registradas (`trading_cycle_tick`, `capture_portfolio_snapshot`, `analyze_performance`).
- Beat emite ticks sin errores persistentes.

---

## 7) Certificacion ML (estado real vs pendiente)

- [ ] 7.1 Validar flag y uso de ML en ciclo

```bash
docker compose -f docker-compose.local.yml exec -T api python - <<'PY'
import os
print("ML_ENABLED=", os.getenv("ML_ENABLED"))
PY
```

- [ ] 7.2 Verificar artefactos de modelo (si aplica)

```bash
docker compose -f docker-compose.local.yml exec -T api sh -lc "ls -la data/ml || true; ls -la models || true"
```

- [ ] 7.3 Verificar evidencia en logs de uso ML o fallback

```bash
docker compose -f docker-compose.local.yml logs --since 15m worker | rg "ML|regime|fallback|predict"
```

Criterio de aceptacion:
- Si `ML_ENABLED=true`: hay evidencia de prediccion real y/o artefactos.
- Si `ML_ENABLED=false`: fallback documentado y aceptado para paper baseline.

Nota:
- `app/services/ml_tasks.py` tiene `analyze_performance` en TODO; no usarlo como criterio de “ML 100% productivo” hasta implementarlo.

---

## 8) Endpoints funcionales de portfolio y estrategia

- [ ] 8.1 Portfolio history

```bash
curl -sf "http://localhost:8000/api/v1/portfolio/history?days=7"
```

- [ ] 8.2 Latest snapshot

```bash
curl -sf "http://localhost:8000/api/v1/portfolio/snapshot/latest"
```

- [ ] 8.3 Estrategia inteligente (solo smoke, en paper)

```bash
curl -sf -X POST "http://localhost:8000/api/v2/strategies/execute_intelligent" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol":"ETHUSDT",
    "account_state":{
      "total_equity":1000,
      "available_balance":500,
      "total_exposure":0,
      "daily_pnl":0,
      "max_drawdown":0,
      "risk_score":0.1
    },
    "paper_mode":true,
    "quick_backtest":false
  }'
```

Criterio de aceptacion:
- Endpoints responden sin 5xx.
- Si faltan snapshots, error controlado y mensaje explicativo (no crash).

---

## 9) Criterio de "100% operativo paper" (Go/No-Go)

Marcar Go solo si se cumplen todos:

- [ ] Infra estable: `db/redis healthy`, `api/worker/beat running`, `migrate exited(0)`.
- [ ] Health y metrics OK (`/health`, `/metrics`, Prometheus ready).
- [ ] Paper mode efectivo (`PAPER_TRADING=true`, sin real mode forzado).
- [ ] Dry-run exitoso.
- [ ] DB con tablas operativas y datos coherentes.
- [ ] Celery con beat+worker activos y tareas clave visibles.
- [ ] Ops watch en `green` sostenido (>= 2 corridas consecutivas).
- [ ] ML estado documentado (activo con evidencia o fallback aceptado temporalmente).

Resultado:
- [ ] **GO** (Paper Certificado)
- [ ] **NO-GO** (acciones pendientes)

---

## 10) Registro de brechas y acciones

| ID | Brecha | Severidad | Evidencia | Accion | Owner | ETA |
|----|--------|-----------|-----------|--------|-------|-----|
| 1  |        |           |           |        |       |     |
| 2  |        |           |           |        |       |     |
| 3  |        |           |           |        |       |     |

---

## 11) Comandos de cierre

Guardar snapshot final de estado:

```bash
docker compose -f docker-compose.local.yml ps > reports/certificacion_paper/final_ps.txt
docker compose -f docker-compose.local.yml logs --since 15m > reports/certificacion_paper/final_logs_15m.txt
cp reports/ops_watch/LATEST.md reports/certificacion_paper/ops_watch_latest.md
```

Opcional (apagar entorno):

```bash
docker compose -f docker-compose.local.yml down
```

