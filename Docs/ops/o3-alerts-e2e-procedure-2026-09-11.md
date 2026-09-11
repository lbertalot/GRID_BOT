# O-3 — Procedimiento E2E alertas (paper) — 2026-09-11

**Modo:** paper-only · **PROMOTE_LIVE: NO**  
**Owner ejecución host:** Desk Lead / SRE (si se dispara ventana stale a propósito)  
**Cursor:** documenta + verifica reglas cargadas; **no** `DEL` Redis HASH; **no** tocar SI.

Antecedente de path Prom→AM→Telegram ya probado:  
[`smoke-breaker-del-fail-closed-2026-08-30.md`](smoke-breaker-del-fail-closed-2026-08-30.md) (`BreakerStoreMissingFailClosed` firing + Telegram + resolved).

---

## Alertas a cubrir (Fase 1 O-3)

| Alerta | Regla en repo | Severidad | Disparo paper-safe sin tocar SI/HASH |
|--------|---------------|-----------|--------------------------------------|
| `PaperSnapshotStale20m` | `paper_obs_p0_rules.yml` | warning | Sí (pausar snapshots ≥25 m) — **requiere OK Desk** (agrega gap A2) |
| `BreakerStoreMissingFailClosed` | idem | critical | **No repetir** en esta sesión: ya PASS 2026-08-30; re-DEL HASH es riesgoso con SI NO-GO |
| `CircuitBreakerActivated` | idem | — | Evitar: SI ya OPEN; no abrir/cerrar frenos |
| `HighDailyDrawdown` | idem | — | Evitar fabricar DD |
| `ReconciliationDiscrepancyDetected` | idem | — | Evitar |
| `CeleryWorkerDown` / `GridbotCeleryWorkersZero` | idem | — | Sí con `--no-deps` stop worker breve — OK Desk (hueco ticks) |

---

## Procedimiento preferido (PaperSnapshotStale20m)

### Preflight

1. `curl -sf http://localhost:8000/health` → `effective_mode=paper`, `force_real_mode=false`, `emergency_stop=false`.
2. Confirmar regla cargada en Prometheus:  
   `curl -sf http://localhost:9090/api/v1/rules | jq '.. | objects | select(.name=="PaperSnapshotStale20m")'`
3. Anotar `portfolio_snapshot_last_unixtime` (job=gridbot-api) y edad actual.
4. **No** tocar Redis `gridbot:breakers:v1`, ledger, racha, N10.

### Disparo (humano / Desk)

```bash
# Solo app; Redis/DB intactos
docker compose -f docker-compose.local.yml stop api worker beat
# Esperar > 20 m (+ for: 5m) ≈ 25–30 m calendario
```

### Confirmación “llegó”

| Canal | Qué verificar |
|-------|----------------|
| Prometheus | `ALERTS{alertname="PaperSnapshotStale20m"}` → `firing` |
| Alertmanager | alerta active warning |
| Telegram CEO | copy de `PaperSnapshotStale20m` (ensayo desfasado; Dinero real: NO) |
| Grafana | panel Paper L0 / Explore `portfolio_snapshot_last_unixtime` |

### Rollback

```bash
docker compose -f docker-compose.local.yml up -d --no-deps api worker beat
# Esperar snapshot fresco <5 m; alerta resolved
```

Anotar en acta: hora start/stop, si Telegram llegó, edad máxima del snapshot. El gap inducido **cuenta para A2** — no hacerlo el día del close 14-sep sin decisión Desk.

---

## Evidencia ya en mano (2026-09-11, sin nuevo disparo)

| Check | Resultado |
|-------|-----------|
| Reglas listadas en Prom runtime | `PaperSnapshotStale20m`, `BreakerStoreMissingFailClosed`, `CircuitBreakerActivated`, `HighDailyDrawdown`, `ReconciliationDiscrepancyDetected`, `CeleryWorkerDown`, `GridbotCeleryWorkersZero` **presentes** |
| AM → API Telegram | `alertmanager.yml` receivers `telegram.critical` / `telegram.warning` → `/api/v1/alerts/telegram/*` |
| Path E2E previo | Smoke 2026-08-30: gauge→Prom firing→AM→Telegram→resolved (**PASS**) |
| Nuevo disparo stale en esta sesión | **No ejecutado** — requiere OK Desk (impacto A2) |

**Estado O-3 para dossier:** procedimiento **DOC OK**; path entrega **probado** (smoke HASH); disparo stale fresco **pendiente decisión Desk** (no bloquea firma paper; sí deja O-3 “parcial E2E reciente”).
