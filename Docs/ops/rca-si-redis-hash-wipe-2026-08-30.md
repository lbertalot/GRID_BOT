# RCA — wipe silencioso de `gridbot:breakers:v1` (SI CLOSED sin Desk Lead)

**Modo:** paper-only · **PROMOTE_LIVE: NO** · `TRADING_ENABLED=false`  
**Severidad:** P0 persistencia de freno (mismo nivel que beat pidfile 2026-08-28)  
**Owner:** `trading-engineering-manager` + `trading-backend-tdd` (gaps A/B/C) · visado Desk Lead  
**Estado:** **prueba SI 5×15 abortada**. HOLD D3 rehidratado. **No reintentar** hasta A/B/C + firma.

Antecedente del mismo síntoma: [`followup-all-hands-p0-2026-08-27.md`](followup-all-hands-p0-2026-08-27.md) (`TYPE none` post-recreate → restore HOLD a mano). Runbook: [`CICD_RUNBOOK.md`](../CICD_RUNBOOK.md) §9.

---

## 0. Veredicto

| Campo | Valor |
|-------|--------|
| Qué falló | El HASH Redis de circuit breakers se **borró** (`DEL gridbot:breakers:v1`) **sin** `deactivate_breaker` de Desk Lead. Un recreate posterior hidrató vacío → SI **CLOSED**. |
| Qué **no** falló | AS-10 / desk auto-remediation (no tocan razón PnL/D3). El contenedor Redis **no** se recreó. LRU `evicted_keys=0`. |
| Prueba 5×15 | **ABORTADA** como observación limpia. Ventana **2026-08-30T01:05:47Z → abort** **inválida**: 0 ticks/closes cuentan. |
| Paper ops | **ITERATE** — HOLD restaurado. Gaps A/B/C pendientes (TDD; ver §7). |
| Live / revenue | **NO-GO**. **PROMOTE_LIVE: NO**. |

---

## 1. Síntoma

Durante el arranque de la prueba controlada SI 5×15 (firma §6 2026-08-29 22:03 ART):

- Redis `TYPE gridbot:breakers:v1` = **`none`** **antes** de `grant_breaker_override.py --trial` y **antes** de `deactivate_breaker("system_integrity")`.
- API `/breakers/summary`: `system_integrity` CLOSED (`active=false`, `operational_state=null`).
- `deactivate_breaker` fue **idempotente** (`before.active False`).
- El Desk Lead **no** había autorizado un CLOSED previo. El contrato post-recreate era: SI **aún REDUCE_ONLY**, HASH intacto.

Esto **no** es el autoclear de PnL (vetado). Es pérdida de persistencia + hydrate-vacío = CLOSED.

---

## 2. Línea de tiempo (UTC)

| t | Hecho | Evidencia |
|---|--------|-----------|
| 2026-08-27T18:55:01.357665 | `activated_at` SI OPEN REDUCE_ONLY (D3 restore; el follow-up documenta el primer restore 16:54:50Z) | JSON recuperado del RDB AOF |
| 2026-08-28T16:41:38Z | Contenedor `gridbot_redis` Started. RestartCount=0 | `docker inspect` |
| 2026-08-29T17:21Z | AOF rewrite. HASH **presente** en `appendonly.aof.13.base.rdb` (`active:true`, `REDUCE_ONLY`, razón D3) | strings/RDB |
| **2026-08-30T01:00:28Z** ±1s | **`DEL gridbot:breakers:v1`** (única DEL de esa key en el increment AOF) | AOF incr, offset ~56135283 |
| 2026-08-30T01:00:29.446535Z | Tick `ba7efc46` SUCCESS en worker **viejo** `celery@d4f20c195891`. SI **aún OPEN in-process** | celery-task-meta `date_done` |
| 01:00:28 → 01:05:47 | HASH `none`; procesos viejos **siguen OPEN en RAM** (hydrate vacío no cierra) | Prom `breaker_state=1` hasta último scrape API viejo |
| **01:05:47Z** | Primer recreate `--no-deps api/worker/beat` (inicio prueba 5×15) | compose / inspect |
| **01:06:25Z** | `TYPE none` + SI CLOSED in-process (API nuevo) | exec Redis + API |
| **01:06:32Z** | Primer scrape Prom `breaker_state{type="system_integrity"}=0` | Prometheus `job=gridbot-api` |
| **01:06:39Z** | Worker: `Circuit breakers activos: []` — ciclo **evaluado sin SI** | logs worker (contenedor ya rotado; citado en sesión) |
| 01:09:27Z | Segundo recreate (t0 con µs) | inspect |
| 01:09:40Z | Worker actual: `Circuit breakers activos: []`, `consecutive_losses=0 threshold=2` | logs |
| 01:10:38Z | `grant --trial` + `deactivate` idempotente | script + Redis HSET closed |
| 01:36:47.527Z | Rehidratación HOLD (este RCA). `activated_at` **recuperado** | HSET |
| 01:37:05Z | Recreate abort (N10, sin `PAPER_TRIAL_*`) | inspect |
| 01:37:40Z | Tick: `consecutive_losses=19 threshold=5 trial_since=None`, SI **activo** | logs worker |

**No contar** ningún tick ni close con `closed_at ≥ 2026-08-30T01:05:47Z` como muestra de la prueba 5×15. Ledger: último close sigue `2026-08-26T15:45:37.370240Z` (0 closes post-t0 en el intento abortado).

---

## 3. Evidencia AOF / Prometheus

### 3.1 Redis AOF

Archivos (contenedor `gridbot_redis`, AOF `appendonly yes`):

- `/data/appendonlydir/appendonly.aof.13.base.rdb` — rewrite **2026-08-29 17:21Z**. Key `gridbot:breakers:v1` **presente**. Campo `system_integrity`: `active: true`, `activated_at: "2026-08-27T18:55:01.357665"`, `operational_state: "REDUCE_ONLY"`, razón D3 (LZF; el ISO de `activated_at` es literal).
- `/data/appendonlydir/appendonly.aof.13.incr.aof` — **1×** `DEL $19 gridbot:breakers:v1` inmediatamente antes del `LPUSH` de `app.services.trading_tasks.trading_cycle_tick` id `ba7efc46-a076-4f12-bdf3-031803ed60d0` (`date_done` **01:00:29.446535Z**). **1×** `HSET` posterior = persist CLOSED del intento de prueba (no es la causa del `TYPE none`).

No es `FLUSHDB` (keyspace ~2290 keys intacto). No es eviction (`evicted_keys=0`, maxmemory-policy allkeys-lru pero uso ~3 MB / 256 MB).

### 3.2 Opcode = `clear_all` / `reset_shared_breakers`

```159:161:app/core/breaker_state_store.py
            self._redis().delete(BREAKER_REDIS_KEY)
```

Único caller de producción-adyacente: `reset_shared_breakers()` en `app/core/circuit_breakers.py` (docstring: *tests / reinicio controlado*). Callers reales: fixtures pytest (`tests/test_s_breakers_b1_b4.py` **sin** forzar `CB_SHARED_STORE=memory`; otros tests monkeypatchean memory).

El host publica Redis de compose en `localhost:6379` (`GRID_BOT/.env` `REDIS_URL=redis://localhost:6379`). Un `reset_shared_breakers()` con backend `auto`/`redis` (pytest sin el `setdefault` de conftest, o `docker exec … python` sin pytest) **borra el HASH de paper**.

AS-10 / `desk_auto_remediation.py` **no** emiten `DEL`. Solo `deactivate` si razón ∈ `{binance_net_fail, binance_auth_fail}`. La razón D3 no entra.

### 3.3 Prometheus (`job=gridbot-api`)

- `breaker_state{type="system_integrity"}` y `breaker_any_open` = **1** de forma continua hasta el último scrape del API **viejo**: **2026-08-30T01:05:47Z**.
- `up{job=gridbot-api}`: hueco **01:06:00–01:06:15Z** (recreate).
- Primer **0**: **01:06:32Z** (API nuevo hidrata vacío).
- `breaker_store_backend{backend="redis"}=1` / `{backend="memory"}=0` en toda la ventana (no fue fallback memory).

Grafana CEO (ventana del incidente): [CEO 00:55–01:40Z](http://localhost:3000/goto/bfwp58fdmx7uoc?orgId=default).

No hay Loki en la instancia Grafana de este entorno; los logs del API/worker **pre**-recreate se pierden con el contenedor.

---

## 4. Causa raíz (dos gaps + un acelerador)

1. **`reset_shared_breakers()` / `clear_all()` puede `DEL` el Redis de paper.** No hay guardrail estructural (bandera explícita) que impida a tests/scripts usar `REDIS_URL=localhost:6379` del compose.
2. **Hydrate vacío = CLOSED.** `CircuitBreakers.__init__` nace `active=False`. `_hydrate_from_store` solo aplica fields presentes; si `load_all()` está vacío, **no** fail-closed hacia el último OPEN conocido.
3. **Guardia de persist incompleto.** `_persist_breaker` salta wipe CLOSED sobre OPEN remoto solo si `remote is not None and remote.active`. Si la key **no existe** (`remote is None`), un persist CLOSED **puede HSET** `active:false`.

El recreate `--no-deps api/worker/beat` **no** borra Redis. Lo que hace es matar el proceso que aún tenía SI OPEN en RAM. El proceso nuevo lee un HASH ya ausente → CLOSED **sin** Desk Lead.

Esto ya estaba pendiente el 27-ago: *«confirmar que el próximo recreate no borre Redis breakers»*. El skip-wipe de persist (Ola 1 logs) **no cubre** `DEL` + hydrate vacío.

---

## 5. Impacto en la prueba 5×15

| Pregunta | Respuesta |
|----------|-----------|
| ¿Hubo decisión Desk Lead de cerrar SI antes del deactivate? | **No.** |
| ¿El grid evaluó ciclos sin SI? | **Sí**, al menos 01:06:39Z, 01:09:40Z, 01:10:38Z (y ticks del override hasta el abort). |
| ¿Hubo closes nuevos? | **No.** Último close ledger `2026-08-26T15:45:37.370240Z`. |
| ¿Se puede usar la muestra? | **No.** Ventana desde **01:05:47Z** invalidada por completo. |

---

## 6. Remediación inmediata (2026-08-30, Opción 1 Desk Lead)

Ejecutado **sin** tocar redis/db contenedores, **sin** live, **sin** wipe ledger/racha 19.

1. **HASH rehidratado** (mismo procedimiento D3 27-ago, con `activated_at` recuperado):
   - `active: true`
   - `activated_at: **2026-08-27T18:55:01.357665**` (literal en RDB AOF; **no** se usó el now de esta restauración)
   - `operational_state: REDUCE_ONLY`
   - razón D3: `Demasiadas pérdidas consecutivas: 19 (All Hands D3 restore HOLD; redis miss post-recreate 2026-08-27)`
   - `transitioned_at: 2026-08-30T01:36:47.527+00:00` (**nuevo**, documentado: esta restauración)
   - `transition_reason`: apunta a este RCA + DEL `01:00:28Z`
2. **Override `--trial` borrado:** `HDEL gridbot:breaker_override:v1 system_integrity` (estaba `granted_at=01:10:38Z`, `ticks_used=16`, watermark t0).
3. **Watermark / overlay revertidos:**
   - compose: `GRID_CONFIG_FILE=grid_config_paper_l0.json`, `PAPER_EARLY_STREAK_WARN=3`, **sin** `PAPER_TRIAL_STARTED_AT` ni `PAPER_TRIAL_STREAK_THRESHOLD`
   - `.env` local (no git): `GRID_CONFIG_HASH=ff6a35fc…7f5c4` (N10)
4. Recreate `--no-deps api worker beat` **01:37:05Z**. Redis intacto (Started 2026-08-28).
5. Verificado post-recreate:
   - `/health` paper · `trading_enabled=false` · `force_real_mode=false`
   - `/breakers/summary` `active_breakers=["system_integrity"]` REDUCE_ONLY, `activated_at` D3
   - Redis `TYPE hash`, override **vacío**
   - env API/worker: `PAPER_TRIAL_*=unset`, hash N10
   - tick 01:37:40Z: `consecutive_losses=19 threshold=5 trial_since=None` · `Circuit breakers activos: ['system_integrity']`

---

## 7. Gaps de raíz — defensa C→B→A **implementada** (2026-08-30)

Contrato TDD en `tests/test_breaker_store_defense_cba.py`. Simulacro `DEL` paper: [`smoke-breaker-del-fail-closed-2026-08-30.md`](smoke-breaker-del-fail-closed-2026-08-30.md) (**PASS**, 13:31:44Z UTC). **Prohibido** reintentar 5×15 hasta firma Desk Lead **nueva**.

| ID | Gap | Mitigación |
|----|-----|------------|
| **C** | `clear_all` no `DEL` Redis sin flag | `GRIDBOT_ALLOW_BREAKER_STORE_WIPE=1`; pytest fuerza `CB_SHARED_STORE=memory` |
| **B** | `remote is None` no HSET closed | anomalía `breaker_store_persist_anomaly_total{kind="closed_over_missing"}` |
| **A** | Hydrate vacío ≠ CLOSED | default `CB_EMPTY_STORE_POLICY=fail_closed` → OPEN+REDUCE_ONLY; alerta `BreakerStoreMissingFailClosed`. Ambiente nuevo a propósito: `fresh` (decisión Desk, no default). Error de lectura Redis **no** se trata como HASH borrado. |

---

## 8. Non-goals

- Live · `FORCE_REAL_MODE` · `TRADING_ENABLED=true`
- Wipe ledger / racha 19
- Reintento 5×15 en esta misma ventana
- Spacing < 100 bps · notional/nivel > 15

---

## 9. Go / no-go

- Paper HOLD D3: **restaurado** post-smoke (ITERATE).
- Observación 5×15 del intento 01:05Z: **REJECT** (contaminada).
- Simulacro `DEL` fail-closed: **PASS** (2026-08-30T13:31:44Z).
- Reintento 5×15: **GO observación** intento 2 — [`trial-si-5x15-2026-08-30.md`](trial-si-5x15-2026-08-30.md) (firma 2026-08-30 11:24 ART). El intento 1 **no** es evidencia.
- **PROMOTE_LIVE: NO.**
