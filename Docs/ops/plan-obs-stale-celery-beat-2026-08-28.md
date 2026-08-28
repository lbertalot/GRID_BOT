# Plan — telemetría stale + Celery en cero (2026-08-28)

**Modo:** paper-only · **PROMOTE_LIVE: NO**  
**Fuentes cruzadas:** diagnóstico Cursor Grafana 8 h + revisión externa (8 tableros).  
**Ancla:** `GRID_BOT/` · HOLD D3 intacto (no reset SI, no spacing, no live).

**Estado 2026-08-28 18:21 ART:** Ola 0 **ejecutada** (beat `/tmp` pidfile, RestartCount=0). Snapshot age ~minutos, tick Flower >0, SI REDUCE_ONLY. Ola 1 (PG) **cerrada**. Evidencia de ejecución: [`exec-ola0-beat-pidfile-2026-08-28.md`](exec-ola0-beat-pidfile-2026-08-28.md). Diffs compose/rules/dashboards **sin commit** (encima de PR #130).

## Marco (acuerdo de ambos)

No es “solo el bot frenado”. El **freno PnL (SI REDUCE_ONLY, racha 19)** está bajo control de diseño. Lo que invalida All Hands / T0 es que **la observabilidad que certifica ese freno está congelada**: snapshot MtM 4+ h, Celery success/1h = 0, workers/API en verde.

Orden: **descongelar pulso (beat) → verificar que el HOLD sigue siendo real → higiene de tableros/alertas → no discutir racha/spacing hasta T0 verde.**

## Causa raíz (no hipótesis)

Logs de `gridbot_beat` (21:01–21:09Z): crash-loop exit 73  
`ERROR: Pidfile (/app/data/celerybeat.pid) already exists. Seems we're already running? (pid: 1)`

El schedule persistente en `/app/data` es correcto (C2). El **pidfile en el mismo volumen** sobrevive al recreate y bloquea beat. Healthcheck `test -f celerybeat-schedule` puede pintar healthy con el proceso muerto.

Eso explica a la vez: snapshot stale, 0 ticks/snapshots/klines/risk, racha “congelada”, `GridBotTickStalled`.

**Hipótesis externa (Postgres / JSON path / fail silencioso):** no es la causa primaria. Queda como **gate Ola 1**: si con beat vivo el snapshot sigue >20 min o hay `pending`/`ERROR` en worker, entonces sí se audita ledger PG.

## Qué no se hace

- Reset / deactivate `system_integrity`.
- Bajar spacing, subir sizing, `TRADING_ENABLED=true`, `FORCE_REAL_MODE`.
- Recrear `redis` o `db`.
- Presentar Grafana 4 h stale como “estado actual” en All Hands (protocolo T0).
- Tratar el −3,54 % ETH como bug: es **validación** del HOLD (no compró en la caída).

---

## Ola 0 — P0 ops, minutos (hoy)

**Owners:** `trading-devops` · `trading-backend-tdd`  
**DoD:** beat Up (no Restarting); Flower `trading_cycle_tick` y `capture_portfolio_snapshot` >0 en 15 min; snapshot age <20 min; SI sigue REDUCE_ONLY; Redis HASH `gridbot:breakers:v1` intacto.

1. Inspeccionar `docker compose logs beat --tail 50` (confirmar pidfile).
2. `rm -f data/celerybeat.pid` (host bind `./data`). **No** borrar `celerybeat-schedule`.
3. Compose: `--pidfile=/tmp/celerybeat.pid`; schedule sigue `/app/data/celerybeat-schedule`.
4. Healthcheck beat: proceso Celery beat (p. ej. `pidof` / `celery inspect ping` no aplica a beat) — **no** `test -f` del schedule.
5. `up -d --force-recreate --no-deps beat` (sin redis/db/api salvo que beat no arranque).
6. Verificar: `/health` paper · `/breakers/summary` SI · Grafana CEO “Última revisión” <20 min.

**TDD:** contrato compose (pidfile no está en `/app/data`) + test de healthcheck.

## Ola 1 — Cerrar la hipótesis Postgres (solo si Ola 0 no basta)

**Owners:** `trading-backend-tdd` · `trading-dba` (solo si hay error PG)

Tras 15 min con beat sano:

| Check | Esperado | Si falla |
|-------|----------|----------|
| Worker logs 4–5 h | sin traceback en snapshot/tick | RCA path JSON vs PG |
| Flower failed | 0 o explicado | no “nada pasó” |
| Redis `celery`/`low` LLEN | ~0 (no cola infinita pending) | inspect reserved/active |
| `desk_tear_capa_a` SoT | JSON hoy (P1 conocido) ≠ causa del stall | no mezclar con beat |

Si snapshot refresca → **cerrar** hipótesis migración. Documentar en nota ops ½ página.

## Ola 2 — Confiar en el freno (Grafana / Prom)

**Owners:** `trading-devops` · `trading-backend-tdd` · `trading-frontend` solo badge/CEO

### 2.1 Doble número de breakers (externo #3)

Causa: **dos jobs scrapean el mismo nombre de métrica**.

- API: `breaker_any_open=1` (SI real).
- Flower/celery: `breaker_any_open=0` (proceso sin store Redis / memoria vacía).

Paper L0 además mezcla `breaker_any_open` (0/1) vs `active_breakers_total` (conteo).

**Fix:** todas las queries de gate con `job="gridbot-api"` (nunca `max()` sin job). Un panel “Freno” = API only. Alerta `BreakerStoreFallbackMemory` acotar `job="gridbot-api"`.

### 2.2 Racha 19 (externo #4)

Tras Ola 0: si `paper_consecutive_losses` sigue 19 **y** snapshot fresco **y** tick OK → racha es SoT HOLD (deadlock SI vs SELL, ya en All Hands). Si racha cambia o tick no evalúa SI → RCA RISK (no relajar umbral 5).

### 2.3 Alertas mentirosas (Cursor)

- `GridBotTickStalled`: dejar de usar `absent(cycle_phase_timestamp)` (el gauge **no se publica** aunque el tick sí corra). Sustituir por Flower `increase(…trading_cycle_tick…succeeded[15m]) == 0`.
- Publicar `cycle_phase_timestamp` en el tick **o** retirar paneles que lo asumen.

**DoD:** pytest contrato dashboards/rules; CI; 0 false-positive Flower memory.

## Ola 3 — P1 no bloquea T0

| Ítem | Owner | Acción |
|------|--------|--------|
| ETH −3,54 % 12:00–14:00 (externo #6) | desk-lead · MM | **DONE** — validación HOLD, ver exec Ola 0. |
| API p95 ~5 s ~17:30 (externo #5) | backend-tdd | **DEFER** — [`defer-p95-pg-pool-2026-08-28.md`](defer-p95-pg-pool-2026-08-28.md). |
| Integrity `_none_` 13:00–17:00 (externo #8) | devops | **DONE** — `or on() vector(0)` / leyenda `n/a` en Health SRE. |
| Pool PG 3 idle (externo #7) | dba | **DEFER** — misma nota; el panel no es `pool_size`. |
| `cash_balance_usdt=0` vs equity 999 | quant | Etiqueta ops ≠ SoT (mismo criterio ROI). |
| Paper L0 default `now-1h` | frontend/obs | **DONE** — default `now-12h`. |

## Checklist All Hands / T0 (antes de citar números)

1. Snapshot age <20 min **ahora**.
2. Celery success/15m >0 (tick + snapshot).
3. SI API = SI Redis = panel Freno (un solo job).
4. Equity citada = `paper_equity_usdt` job=api, **no** ROI ops.
5. Hueco 11:44–13:44 ART = recreate/obs, no wipe ledger.
6. **PROMOTE_LIVE: NO.**

## Orden de ejecución

1. Ola 0 beat (humano, minutos).  
2. Esperar 15 min · Grafana CEO + Celery.  
3. Ola 1 solo si stale persiste.  
4. Ola 2 TDD alertas/queries (PR).  
5. Ola 3 docs + cosmética.  
6. Nada de racha/spacing/grid hasta T0 verde.

**Veredicto post Ola 0:** pulso **vivo** — All Hands puede citar snapshot/tick actuales. La ventana 4 h stale queda como incidente obs cerrado, no como estado. HOLD D3 + **PROMOTE_LIVE: NO.** ITERATE paper.
