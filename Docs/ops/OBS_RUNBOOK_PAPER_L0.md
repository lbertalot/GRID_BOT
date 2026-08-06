# OBS Runbook — Paper L0 (digest AT_RISK → paneles)

**Owner:** devops + desk · **Sprint:** S-WAVE-E-OBS  
**URLs:** Grafana http://localhost:3000 · Prom http://localhost:9090 · AM http://localhost:9093 · API :8000

---

## Si el digest dice AT_RISK

| Señal digest / log | Dónde mirar ahora | Tras E3 (Health SRE) |
|--------------------|-------------------|----------------------|
| `effective_mode` | `GET /health` / trading-mode | Panel **Mode (paper=1)** |
| Equity / Δ E_0 | `paper_telemetry/*.json` + Telegram | **Paper equity USDT** |
| Snapshot age | logs `[SnapshotAgent]` | **Snapshot age** |
| Pipeline degraded | logs worker `PipelineHealth` | **Pipeline degraded** |
| Breakers | Paper L0 `breaker_any_open` | mismo + Health SRE row infra |
| `-1021` / Binance | logs api | **Binance errors by code** |
| Breakers API≠worker | log noise + digest | E5 (Redis única fuente) |

**No** usar dashboard **Rentabilidad** (`profit_total_usdt`) como SoT en paper L0.

---

## Checklist obs rápido

```bash
docker compose -f docker-compose.local.yml ps
curl -sS http://localhost:8000/health | jq .trading
curl -sS 'http://localhost:9090/api/v1/targets' | jq '.data.activeTargets[]|{job:.labels.job,health}'
curl -sS -u admin:gridbot123 'http://localhost:3000/api/search?type=dash-db' | jq '.[].title'
```

Dashboards desk: **GridBot Health SRE (paper)** · **GridBot Paper L0** · Prometheus targets.

---

## Alertas paper-aware (P0)

Archivo: `docker/prometheus/rules/paper_obs_p0_rules.yml`  
Mute writes=0 en paper: `pipeline_ingestion_rules.yml` (requiere gauge `trading_effective_mode{mode="paper"}`).

Hasta que backend emita series, varias reglas quedan **inertes** (sin muestras) — esperado; no reiniciar ventana.
