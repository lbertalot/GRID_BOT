# Contrato métricas S-OBS-P0 / E3 (devops ↔ backend)

**Fecha:** 2026-08-06  
**Sprint:** S-WAVE-E-OBS · slices **E1** (devops bosquejo) + **E3** (backend emit + dash live)  
**Modo:** paper-only · **PROMOTE_LIVE:** NO  
**Gap:** `Docs/ops/OBS_GAP_LOGS_VS_GRAFANA_2026-08-06.md` P0.1–P0.6

---

## Objetivo

Una sola URL desk (**GridBot Health SRE**) cubre señales L4–L9 del gap: mode, equity SoT, snapshot age, pipeline degraded, errores Binance — alineadas a logs/`/health`, no a `profit_total_usdt`.

---

## Métricas a emitir (owner: `trading-backend-tdd`)

| Nombre Prom | Tipo | Labels | Semántica | Notas |
|-------------|------|--------|-----------|-------|
| `trading_effective_mode` | Gauge | `mode` | one-hot `1` en el mode efectivo (`paper` / `real_blocked` / `real_armed` / …) | Misma fuente que `/health` → `effective_mode` |
| `paper_equity_usdt` | Gauge | — | Última equity SoT del ledger/serie | **No** usar `gridbot_profit_loss` ni `profit_total_usdt` |
| `paper_equity_e0_usdt` | Gauge | — | E_0 anclado (último `daily_close` o freeze) | Desk Δ% |
| `paper_equity_samples` | Gauge | — | Conteo samples en serie | Integridad ventana |
| `portfolio_snapshot_last_unixtime` | Gauge | — | Unix ts del último snapshot MtM OK | = `snapshot_ts` del brief |
| `pipeline_health_degraded` | Gauge | — | `1` degraded / `0` ok tras check Celery | Paper-aware en **E4** (idle ≠ FAIL) |
| `pipeline_health_table_ok` | Gauge | `table` | Ya definido en `app/core/metrics.py` | Setear al final del check |
| `db_writes_total` | Counter | `table,operation,status` | Ya definido | **Emitir siempre** (aunque 0) o alertas con `absent()` |
| `binance_api_errors_total` | Counter | `code,phase` | Ya definido | Incrementar en path PnL (`-1021`, etc.) |

### Opcional P1 (no bloquea E3)

| Nombre | Uso |
|--------|-----|
| `desk_digest_global_status` | Mapear ON_TRACK=0 / AT_RISK=1 / OFF_TRACK=2 |
| `desk_digest_last_success_unixtime` | Último digest Telegram OK |

---

## Consumidores devops (ya bosquejados)

| Artefacto | Path |
|-----------|------|
| Dashboard Health SRE | `docker/grafana/dashboards/gridbot-health-sre.json` |
| Alertas paper-aware | `docker/prometheus/rules/paper_obs_p0_rules.yml` |
| Guard pipeline idle | `docker/prometheus/rules/pipeline_ingestion_rules.yml` (mute si `mode=paper`) |
| Runbook cierre | `Docs/ops/RUNBOOK_DAILY_CLOSE_PAPER_L0.md` |
| Runbook obs | `Docs/ops/OBS_RUNBOOK_PAPER_L0.md` |

---

## DoD conjunto E3 (testable)

1. Tras 1 ciclo PipelineHealth + 1 scrape: queries en `:9090` devuelven series (no EMPTY).
2. Grafana **Health SRE** muestra mode=paper, equity≈ledger, snapshot age < 20m en steady state.
3. Alertas: mode≠paper → fire; snapshot stale → fire; `-1021` rate → fire; trades/balances=0 en paper idle → **no** spam.
4. Tests unitarios backend de set/inc métricas; smoke devops checklist abajo.
5. Paper-only: sin `FORCE_REAL_MODE`, sin wipe telemetry.

### Smoke post-merge backend

```bash
curl -sS 'http://localhost:9090/api/v1/query?query=trading_effective_mode' | jq .
curl -sS 'http://localhost:9090/api/v1/query?query=paper_equity_usdt' | jq .
curl -sS 'http://localhost:9090/api/v1/query?query=pipeline_health_degraded' | jq .
curl -sS 'http://localhost:9090/api/v1/query?query=portfolio_snapshot_last_unixtime' | jq .
curl -sS 'http://localhost:9090/api/v1/query?query=sum(binance_api_errors_total)' | jq .
```

---

## Naming locked (evitar drift)

Brief E3 dice: `mode`, `paper_equity`, `snapshot_ts`, `pipeline_degraded`, `binance_errors`.  
**Nombres canónicos Prometheus** = tabla de arriba (`trading_effective_mode`, `paper_equity_usdt`, `portfolio_snapshot_last_unixtime`, `pipeline_health_degraded`, `binance_api_errors_total`). No inventar aliases sin actualizar dash+rules juntos.
