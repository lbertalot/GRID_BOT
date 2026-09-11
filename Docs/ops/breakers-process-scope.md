# Breakers — alcance de proceso (B5)

Paper-safe. S-BREAKERS (#51) unificó el estado **in-process** vía `get_shared_breakers()`. Residual B5: API FastAPI y worker Celery son procesos distintos.

## Veredicto

| Opción | Estado | Notas |
|--------|--------|-------|
| **A — Redis HASH compartido** | **Go (MVP)** | Redis ya está en Compose/Celery (`REDIS_URL`). Persistimos trips/open + cooldown anti-flap. |
| B — Alerta en restart + doc | Diferido | Solo si Redis no estuviera disponible; no cierra el hueco de estado. |

## Contrato

| Clave Redis | Tipo | Contenido |
|-------------|------|-----------|
| `gridbot:breakers:v1` | HASH | field = nombre breaker; value = JSON (`active`, `activated_at`, `reason`, `last_activation_ts`, `last_activation_reason`, `activation_count`) |

| Env | Default | Efecto |
|-----|---------|--------|
| `CB_SHARED_STORE` | `auto` | `auto` → Redis si ping OK, si no memory; `redis` / `memory` forzados |
| `CB_COOLDOWN_SECONDS` | `300` | Anti-flap (B4); el timestamp/razón viven en el store |
| `CB_EMPTY_STORE_POLICY` | `fail_closed` | Qué hacer si Redis **responde** y no hay field `system_integrity`. **Default consciente:** ambiente nuevo (staging / 2ª instancia paper) **nace OPEN+REDUCE_ONLY**. Desk desbloquea con `deactivate` auditado, o setea `fresh` **antes** del primer arranque si el vacío es esperado. `fresh` / `new` / `empty_ok`: vacío = CLOSED, sin alerta ni persist. |
| `GRIDBOT_ALLOW_BREAKER_STORE_WIPE` | unset | Única bandera que autoriza `DEL gridbot:breakers:v1`. Tests/host pytest **no** la setean. Paper/prod: no definirla. |

Módulo: `app/core/breaker_state_store.py`. Wiring: `CircuitBreakers(store=...)` + `get_shared_breakers()`.

## Arranque genuinamente nuevo vs incidente

| Situación | Lectura Redis | Policy | Resultado |
|-----------|---------------|--------|-----------|
| Paper L0 / prod (default) | HASH o field SI **ausente** (HGETALL OK) | `fail_closed` | OPEN + REDUCE_ONLY, persist OPEN, gauge sticky, alerta Grafana+Telegram |
| Staging / 2ª instancia **vacía a propósito** | Ídem | `fresh` | CLOSED, sin alerta, sin HSET closed |
| Timeout / Redis caído | `last_load_ok=False` | cualquiera | **No** fail-closed ni persist (no pisar un HASH que sigue ahí) |

## Defensa C→B→A (RCA 2026-08-30)

1. **C — cerradura:** `RedisBreakerStateStore.clear_all()` no hace `DEL` sin `GRIDBOT_ALLOW_BREAKER_STORE_WIPE=1`. `reset_shared_breakers()` de pytest usa memory (`tests/conftest.py` fuerza `CB_SHARED_STORE=memory`).
2. **B — alarma de escritura:** `_persist_breaker` closed con `remote is None` **no** HSET. Incluye `deactivate` de una key ya ausente (anomalía; no fabrica un closed). `deactivate` de un OPEN existente sí persiste closed.
3. **A — protocolo si igual entraron:** hydrate durable + SI ausente + policy default → fail-closed REDUCE_ONLY (no asume CLOSED).

## Fail-soft

- Lectura/escritura Redis fallida → log + `breaker_store_sync_errors_total{op=...}`; el proceso sigue con estado local.
- Tests unitarios: `CB_SHARED_STORE=memory` (fixture B5 / `reset_shared_breakers`).

## Métricas

- `breaker_store_backend{backend="redis|memory"}` — qué backend está activo.
- `breaker_store_sync_errors_total{op}` — errores de sync (`clear_denied` si alguien pide wipe sin flag).
- `breaker_store_missing` — gauge sticky 1 en el proceso que fail-closed (alerta Prom `BreakerStoreMissingFailClosed`, 30s).
- `breaker_store_fail_closed_total` — conteo de fail-closed.
- `breaker_store_persist_anomaly_total{kind="closed_over_missing"}` — intento de HSET closed sobre vacío.

## Residual

- No hay pub/sub: cada consulta hace HGETALL (aceptable para frecuencia de breakers).
- Contadores Prometheus siguen siendo por proceso (edge-trigger local); el estado open/closed sí es compartido.
- No toca `grid_config_paper_l0*` ni freeze L0.

## Recuperación de proceso (sin wipe)

Parar el ciclo o recrear API/worker/beat **nunca** borra Redis HASH ni ledger.

```bash
# Solo procesos de app. Redis y Postgres siguen. Sin -v.
docker compose -f docker-compose.local.yml up -d --no-deps --force-recreate api worker beat
```

| Fallo | Qué hacer | Qué no hacer |
|-------|-----------|--------------|
| Emergency stop | `EMERGENCY_STOP=true` en `.env` local + recreate `--no-deps` api/worker/beat | `DEL` Redis, `down -v`, reset racha |
| Redis caído | el store **no** fail-closed ni persiste (no pisar HASH). Subir Redis; **no** `DEL gridbot:breakers:v1` | wipe, override SI de PnL/NO-GO |
| Postgres caído | no colocar órdenes (`fail_closed: postgres unavailable`). Subir `db`; recreate `--no-deps` api/worker | migraciones destructivas, borrar ledger |
| Ticker caído | no marcar equity ni colocar (`fail_closed: ticker unavailable`). No inventar mid | forzar precio, live |
| HASH SI ausente | fail-closed REDUCE_ONLY (defensa C→B→A) | `GRIDBOT_ALLOW_BREAKER_STORE_WIPE` |

## Checklist humano R-6 (API key sin retiro)

En Binance → Gestión de API, **sin pegar la key ni el secret** en chat/git:

1. Restricción de IP confiables: ON.
2. Permiso de **retiro / withdraw: OFF**.
3. MASTER spot lectura+trade; READ solo lectura. Sin futuros.
4. Anotar “verificado YYYY-MM-DD” en el acta desk. `PROMOTE_LIVE: NO`.
