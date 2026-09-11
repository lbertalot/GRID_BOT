# Smoke — `DEL gridbot:breakers:v1` fail-closed (paper)

**Modo:** paper-only · **PROMOTE_LIVE: NO** · `TRADING_ENABLED=false`  
**Fecha:** 2026-08-30 (UTC)  
**Criterio:** mismo que el 2º ciclo del pidfile beat — stack real, no solo pytest.

Antecedente: [`rca-si-redis-hash-wipe-2026-08-30.md`](rca-si-redis-hash-wipe-2026-08-30.md). Defensa C→B→A ya en código.

---

## Veredicto

| Campo | Valor |
|--------|--------|
| Resultado | **PASS** |
| Tras `DEL` | SI **OPEN + REDUCE_ONLY** (no CLOSED). Razón `breaker_store_missing`. |
| Alerta | Gauge `breaker_store_missing=1` · Prom `BreakerStoreMissingFailClosed` **firing** · Telegram enviado (copy CEO). |
| Limpieza | HASH D3 restaurado (`activated_at` 2026-08-27T18:55:01.357665). Gauge 0. Alerta **resolved**. Redis **no** recreado. |
| 5×15 | **NO-GO** — hace falta firma Desk Lead **nueva**. Este smoke no autoriza reintento. |
| Live | **NO**. |

---

## Línea de tiempo (UTC)

| t | Hecho |
|---|--------|
| 13:31:12Z | Backup HASH → `Docs/ops/smoke-breaker-del-backup-20260830T133112Z.json` |
| 13:31:12Z | `POST /-/reload` Prometheus (regla `BreakerStoreMissingFailClosed` ausente hasta entonces) |
| 13:31:15Z | `restart` api/worker/beat. Redis Started sigue **2026-08-28T16:41:38Z**. SI D3 intacto, `breaker_store_missing=0` |
| **13:31:44Z** | `DEL gridbot:breakers:v1` → `TYPE none` |
| 13:31:45Z | `GET /breakers/summary` → `active=true`, `REDUCE_ONLY`, razón `breaker_store_missing…`, `activated_at` nuevo |
| 13:31:45Z | Persist recreó HASH OPEN. Log ERROR fail-closed. Telegram: *Freno: se perdió el estado de protección* |
| 13:31:46Z | Métricas API: `breaker_store_missing=1`, `breaker_store_fail_closed_total=1` |
| 13:32:06Z | Prom alerta `pending`→ eval |
| 13:32:36Z | Alertmanager **active** `BreakerStoreMissingFailClosed` critical |
| 13:33:50Z | Prom `ALERTS{alertname=…}` **firing** |
| 13:34:00Z | HSET restore backup D3 |
| 13:34:14Z | restart api/worker/beat. SI D3, `breaker_store_missing=0`, paper |
| 13:35:25Z | Alerta **resolved** (Prom + AM). `TYPE hash` |

---

## Qué se comprobó (vs el incidente 01:00Z)

| Antes (incidente) | Este smoke |
|-------------------|------------|
| Hydrate vacío = CLOSED | Hydrate vacío = REDUCE_ONLY |
| Nadie avisó | Telegram inmediato + alerta Prom 30s |
| HASH `none` hasta recreate | Persist fail-closed reescribe HASH OPEN en ~1s |

---

## Grafana

- [Paper L0 · breaker any open / store_missing](http://localhost:3000/goto/efwqwyvprtxxcf?orgId=default)
- [CEO · Freno / racha](http://localhost:3000/goto/ffwqwyyxm4f7kc?orgId=default)
- [Explore · `breaker_store_missing` + `ALERTS`](http://localhost:3000/goto/cfwqwz6jvz20we?orgId=default)

Ventana: `2026-08-30T13:25:00Z` → `13:40:00Z`.

---

## Non-goals (respetados)

- No `FORCE_REAL_MODE` / `TRADING_ENABLED=true`
- No recreate redis/db
- No overlay `PAPER_TRIAL_*`
- No wipe ledger / racha 19
- No `deactivate` Desk
