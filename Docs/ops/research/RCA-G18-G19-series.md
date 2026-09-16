# RCA — G18 / G19 huecos A2 en `paper_equity_series` (stack vivo)

**Fecha:** 2026-09-13  
**Owner:** `trading-engineering-manager` · `trading-quant-engineer` · `trading-backend-tdd`  
**Severidad:** P0 cobertura SoT (A2) · paper-only · **PROMOTE_LIVE: NO**  
**Contrato:** [`Docs/squad/action-plan-post-retro-30d-GRID_BOT-2026-09-13.md`](../../../../Docs/squad/action-plan-post-retro-30d-GRID_BOT-2026-09-13.md) WS B

---

## 1. Síntoma

Dos gaps >2 h **después** del corte del dossier (2026-09-11T20:42Z), con equity plana y 0 closes nuevos:

| # | Rango UTC | Duración | Clase |
|---|-----------|----------|--------|
| **G18** | 2026-09-11T21:05:07Z → 23:16:01Z | 2,18 h | SoT serie; stack vivo |
| **G19** | 2026-09-12T17:31:49Z → 22:31:49Z | 5,00 h | SoT serie; stack vivo |

Durante ambos intervalos: `capture_portfolio_snapshot` OK ~15 min, `pipeline_health` escribe reports, digest desk AT_RISK, SI REDUCE_ONLY. **≠** gap 126 h host-off (04→09-sep). **≠** O-3 (entrega de alertas).

Fuente: retro §8.1.

## 2. Causa raíz

Persistencia de la serie es **read-modify-write de archivo completo** por proceso, sin lock distribuido ni merge:

1. `get_paper_equity_series()` hidrata un singleton **por proceso** (`_series`) desde JSON.
2. `PaperEquitySeries.record()` hace `self._samples.append` en RAM y `_autosave()`.
3. `_atomic_write_json` vuelca **todo** el payload a `.tmp` y `Path.replace` — no hay merge con disco.
4. Celery prefork: cada worker tiene su propia copia. El último `replace` **gana**; samples del otro proceso se pierden → hueco A2 con stack «Up».
5. `_autosave` **traga** excepciones (`logger.error` + return) → fallo de I/O también es hueco silencioso.
6. El ledger ya documenta prefork (`reload_paper_ledger_from_disk`); la serie **no** recarga bajo escritura.

Código: [`app/core/paper_equity_ledger.py`](../../../app/core/paper_equity_ledger.py) (`record` ~L979, `_autosave` ~L1185, `_atomic_write_json` ~L1194, `get_paper_equity_series` ~L1298).

Callers concurrentes típicos: `compute_paper_portfolio_value` (snapshot Celery 900 s) y cualquier tick/IC que re-grabe la serie en otro child.

## 3. Qué no es

| Hipótesis | Veredicto |
|-----------|-----------|
| Host/compose off (clase 126 h) | Descartada (logs/health vivos) |
| O-3 / `PaperSnapshotStale20m` | Distinto: alerta vs escritura SoT |
| Ticker ausente (`compute_paper_portfolio_value` → `None`) | Hueco A2 **intencional** (A6); no explica 2–5 h con snapshots OK |
| File-lock local (`flock` / `.lock` en volumen) | **Prohibido** — no serializa entre contenedores Docker |

## 4. Spec lock interim (DoD)

**Motor:** Redis (`REDIS_URL` del compose). Reutilizar cliente de [`app/core/distributed_lock.py`](../../../app/core/distributed_lock.py); **no** reutilizar el degradado `RedisError → ejecutar sin lock`.

| Parámetro | Valor |
|-----------|--------|
| Key | `lock:paper:equity_series` (no `lock:celery:*`) |
| TTL / auto-release | **5 s** (anti-deadlock OOM/crash) |
| Acquire | blocking; `blocking_timeout` ≥ TTL (10 s) para no **saltar** el sample |
| Sección crítica | reload JSON → append sample → `save()` (errores **no** swallow) |
| Fail-closed | si Redis no responde y el lock está exigido: **no** escribir |
| File-lock | **prohibido** |

PG advisory lock queda para el spike A / T2 (serie en `paper_ledger_equity_samples`), no para este interim.

Pytest: `PAPER_EQUITY_SERIES_LOCK=0` por defecto (no romper tests sin Redis). Paper compose: lock **on** (default `"1"`).

## 5. Test de carga

- ≥2 **procesos** (equivalente operativo a pytest-xdist workers; la carrera es prefork, no threads).
- **1000** `record()` al mismo `paper_equity_series.json`.
- Duración **&lt;30 s**.
- Criterio: `len(samples) == 1000` y **0 gaps** clase G18/G19 (`max_gap_seconds < 7200` con timestamps 1 s).

## 6. Fallback latencia

Si p95 del hold del lock síncrono **&gt;50 ms** en hot path `_autosave`/`record`:

- **No** alargar TTL a ciegas.
- Proponer cola Celery dedicada que consolide samples (el tick no espera el JSON).
- Medición vive en el test de carga (duraciones por `record`). Pre-T0: implementar lock síncrono; cola solo si el test o runtime supera el umbral.

## 7. Relación con WS A

Lock+reload **no espera** al spike PG. Decisión «serie SoT = PG» se une en **T2**.

## 8. Fix / validación

| Paso | Estado |
|------|----------------|
| Este RCA | escrito |
| TDD lock Redis TTL 5 s + reload bajo lock | **hecho** (`PaperEquitySeries._record_with_distributed_lock`) |
| Test 1000 writes / 2 procesos / &lt;30 s / 0 gaps | **hecho** (`tests/test_paper_equity_series_g18_lock.py`) |
| Despliegue en stack paper real (`gridbot_worker`/`gridbot_beat`) | **hecho 2026-09-15T11:36:16Z** — el código con el fix ya estaba en el volumen bind-mounted desde el sprint Pre-T0, pero los procesos Celery (arrancados 2026-09-11T21:04, `RestartCount=0`) seguían corriendo el código **anterior** al fix en memoria. Se reinició `gridbot_worker` + `gridbot_beat` para que reimporten el módulo. `PAPER_EQUITY_SERIES_LOCK` no requirió cambio de compose: `_paper_series_lock_enabled()` default es `"1"` (on) y `REDIS_URL=redis://redis:6379` ya estaba wireado en el worker (breakers ya lo usaban). |
| Smoke test post-restart | **PASS 2026-09-15T11:37:19Z** — 3 llamadas concurrentes a `capture_portfolio_snapshot` (`docker exec ... celery call`, disparadas en paralelo) → 3/3 `SnapshotAgent` succeeded, serie pasó de 887 a 890 samples (+3, 0 pérdidas), sin excepción `PaperLedgerError`. Evidencia de que el lock serializa correctamente bajo contención real, no solo en el test sintético de pytest-xdist. |
| **Ventana de verificación 72h (criterio de cierre G18/G19)** | **EN CURSO.** Inicio: `2026-09-15T11:36:16Z` (restart worker). Fin objetivo: `2026-09-18T11:36:16Z`. Criterio: 0 gaps &gt;2h nuevos en `paper_equity_series.json` durante esa ventana, medidos sobre timestamps posteriores al restart (los 19 gaps históricos —el último G19 el 2026-09-12— no cuentan para este cierre, son la razón por la que existe el fix). Estado al momento de escribir: 0 gaps en los primeros ~2 min post-restart (smoke test); insuficiente para declarar el criterio cumplido. |
| Dual-write / flip PG serie | **fuera de alcance de este RCA** — ver spike-pg-ledger-flip.md §5 (decisión T2). Postgres (`paper_ledger_equity_samples`) tiene 81 filas de un backfill puntual 2026-08-26→27, **no** recibe escritura continua; no sustituye a este lock hoy. |

**Por qué el lock sigue siendo necesario aunque el cutover a PG esté en curso (no es doble trabajo):** el flip completo de ADR-016 (cycles/fills/accounts + serie) requiere índices `CONCURRENTLY`, dual-write validado y script `down` probado (spike-pg-ledger-flip.md §2-3) — trabajo de DBA que **no se ejecuta en este sprint** ("no ejecutar el flip en Pre-T0"). Mientras esa migración no cierre, `paper_equity_series.json` sigue siendo el único SoT de la serie, y el lock es el único mecanismo que evita G18/G19 en ese SoT. Cuando el flip mueva la serie a `paper_ledger_equity_samples` con escritura transaccional (INSERT atómico, no read-modify-write), el lock de Redis queda redundante y se puede retirar — pero esa decisión es explícitamente de **T2** (spike §5), no de este RCA.

**PROMOTE_LIVE: NO.** No wipe de `paper_equity_series.json`. No se tocó Redis/breakers/SI durante el restart (`GRIDBOT_ALLOW_BREAKER_STORE_WIPE` sigue unset).
