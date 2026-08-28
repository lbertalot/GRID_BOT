# Ejecución Ola 0–3 — beat pidfile (2026-08-28 18:21 ART)

**Modo:** paper-only · **PROMOTE_LIVE: NO**  
**Plan:** [`plan-obs-stale-celery-beat-2026-08-28.md`](plan-obs-stale-celery-beat-2026-08-28.md)

## Ola 0 — cerrada

| Check | Resultado |
|-------|-----------|
| Pidfile host | `rm -f data/celerybeat.pid` — schedule **no** tocado |
| Beat | Up 7 min healthy · RestartCount=0 · pid `/tmp` vivo |
| Recreate | `--no-deps beat` + prometheus + grafana. **No** redis/db |
| `/health` | `paper_trading=true` · `trading_enabled=false` · `effective_mode=paper` |
| SI | REDUCE_ONLY · Redis `gridbot:breakers:v1` = HASH |
| Snapshot age | **~7 min** (`portfolio_snapshot_last_unixtime` job=api) |
| Tick Flower 15m | **~7** `trading_cycle_tick` succeeded |
| Colas Redis | `LLEN celery=0` `LLEN low=0` |

Compose: `--pidfile=/tmp/celerybeat.pid`; healthcheck `kill -0` del pid, no `test -f` del schedule.

## Ola 1 — hipótesis Postgres **cerrada**

Con beat vivo el snapshot refrescó en el mismo minuto del recreate (sidecar `captured_at_unix` 18:21 ART). Worker sin traceback en tick/snapshot; colas vacías. El stall de 4+ h **no** fue migración PG ni fail silencioso de JSON path: fue beat crash-loop exit 73 por pidfile en el volumen.

Racha 19 + `latest_closed_at=2026-08-26T15:45:37Z` se revalidan en tick vivo (~1/min). El HOLD es real, no telemetría congelada.

## Ola 2.2 — racha

`paper_consecutive_losses{job="gridbot-api"}=19` con snapshot fresco y tick OK → SoT HOLD (deadlock SI vs SELL). **No** relajar umbral 5. `breaker_any_open`: API=1, Flower=0 — citar solo job=api.

Alertas `GridBotTickStalled` / `PaperSnapshotStale20m` / `BreakerStoreFallbackMemory`: motor Prom **inactive**; serie `ALERTS` residual del TSDB se fue a vacío ~5 min post-recreate.

## Ola 3 — ETH −3,54 % (12:00–14:00 ART)

La caída de ETH **no es incidente**. Bajo SI REDUCE_ONLY el bot no compró en la bajada: es **validación del HOLD**. No abrir RCA de ejecución. p95 API ~17:30 y pool PG “3 idle”: **DEFER** (no freeze).

## T0 / All Hands (ahora)

1. Snapshot age <20 min — **sí**.
2. Celery success/15m >0 — **sí**.
3. Freno = SI API = Redis HASH — **sí** (ignorar Flower breaker=0).
4. Equity = ledger USDT ≈ 999.02 — **sí**. No citar ROI ops.
5. Hueco 11:44–13:44 ART = recreate/obs, no wipe ledger.
6. **PROMOTE_LIVE: NO.**

Grafana (12 h): [Paper L0](http://localhost:3000/goto/bfwky5ru54uf4a?orgId=default) · [Celery](http://localhost:3000/goto/efwky5tw34mwwa?orgId=default) · [CEO](http://localhost:3000/goto/bfwky5vvj82yod?orgId=default).

**Veredicto:** pulso descongelado · HOLD intacto · ITERATE paper · revenue/live **NO-GO**.

## Pendientes (cerrados 2026-08-28 19:10 ART)

- Commit/push Ola 0 → PR #130 (pidfile `/tmp`, alertas Flower, dashboards, tests, esta nota).
- p95 API + pool PG idle → **DEFER** documentado: [`defer-p95-pg-pool-2026-08-28.md`](defer-p95-pg-pool-2026-08-28.md).
- All Hands T0.5 (obs viva; no citar Grafana 4 h stale) → [`t0-obs-frescura-all-hands-2026-08-28.md`](t0-obs-frescura-all-hands-2026-08-28.md).
