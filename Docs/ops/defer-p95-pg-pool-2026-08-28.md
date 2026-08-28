# DEFER — API p95 ~17:30 y pool PG “3 idle” (2026-08-28)

**Modo:** paper-only · **PROMOTE_LIVE: NO**  
**Plan:** [`plan-obs-stale-celery-beat-2026-08-28.md`](plan-obs-stale-celery-beat-2026-08-28.md) Ola 3  
**No es freeze.** No change de `pool_size`, timeouts ni spacing.

## Por qué DEFER (no es “lo vimos y listo”)

Ambos hallazgos salieron del review Grafana **mientras beat estaba muerto** (pidfile stale, ~11:37–18:21 ART) y/o durante recreates de Prom/Grafana. No hay evidencia de que sean degradación del path de órdenes paper bajo HOLD.

Reabrir **solo** si, con beat healthy + snapshot age &lt;20 min + tick Flower &gt;0:

1. p95 API &gt; 2 s sostenido ≥15 min **fuera** de una ventana de `compose recreate`, o
2. se reactiva el grid (SI no REDUCE_ONLY) y hay que dimensionar el pool real.

Hasta entonces: no RCA, no ticket de capacity, no tocar freeze.

---

## API p95 ~5 s ~17:30 ART (externo #5)

**Dónde se vio:** panel “API Latency p95” (`histogram_quantile` sobre `http_request_duration_seconds_bucket{job="gridbot-api"}`) en Pipeline Ingestion.

**Lectura:** un spike aislado en HOLD no es latencia de ejecución (no hay BUY). Candidatos, en este orden, el día que se reabra:

1. Recreate Prometheus/Grafana o hueco de scrape (hubo uno ~11:44–13:44 ART el mismo día).
2. Llamada Binance `account` / ticker en el scrape o en un tick (worker, no API).
3. Lock Redis `trading_cycle` o hydrate `obs_gauges` + SQL `MAX(captured_at)` en `/metrics`.
4. Postgres (último).

**Owner al reabrir:** `trading-backend-tdd`. Ventana a trazar: 15 min alrededor del spike, logs API `request` + Prom `http_request_duration_seconds`. **Sin** bajar timeouts ni “optimizar” el freeze.

---

## Pool PG “3 idle” (externo #7)

**Dónde se vio:** `gridbot-pg-sre`, serie `pg_stat_activity_count{state="idle"}` con leyenda “idle (pool)”.

Eso **no** es el `pool_size` de SQLAlchemy (código: 10). Es backends Postgres en `state=idle` (`pg_stat_activity`). Con HOLD, 3 sesiones idle (API + worker + beat o exporter) es el patrón esperado, no saturación.

Al reabrir (pre-reactivación de grid):

```sql
SELECT state, count(*) FROM pg_stat_activity
WHERE datname = 'gridbot' GROUP BY 1;
```

Cruzar con `pool_size` / `max_overflow` de la app. Si idle ≈ conexiones abiertas y `active` ≈ 0, el panel mintió el nombre, no el pool.

**Owner al reabrir:** `trading-dba`. **DEFER** hasta que SI no esté REDUCE_ONLY o haya un incidente de `too many connections`.
