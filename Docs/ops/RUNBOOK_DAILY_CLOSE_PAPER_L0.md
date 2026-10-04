# Runbook — Cierre diario paper L0 (día N)

**Owner:** `trading-devops` (E1) · apoyo desk/backend  
**Modo:** PAPER-ONLY · **PROMOTE_LIVE:** NO · **No wipe** `paper_telemetry`  
**Ventana:** **23:30–00:30 UTC** (ancla `00:00` ±30m)  
**Freeze:** `config_hash` = sidecar L0 (`630abf63…`) · sizing 200

---

## Pre-check (≈23:15 UTC)

```bash
cd /path/to/gridbot

docker compose -f docker-compose.local.yml ps
curl -sS http://localhost:8000/health | jq .trading
# Esperado: effective_mode=paper, paper_trading=true, trading_enabled=false, force_real_mode=false

# Hash + próxima ventana (SIEMPRE dentro del worker — el host puede resolver otro hash)
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/capture_paper_e0_daily_close.py --dry-run
```

Abortar si: `effective_mode≠paper`, `FORCE_REAL_MODE` seteado, `ML_ENABLED=true`, o `config_hash` ≠ freeze.

---

## Durante la ventana (23:30–00:30Z)

**Path preferido:** dejar que Celery `capture_portfolio_snapshot` (beat ~900s) tome la marca con `daily_close_at`.

**Path manual (backup E1):**

```bash
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/capture_paper_e0_daily_close.py --write
```

Fuera de ventana el script sale `2` y **no escribe**. No forzar con clock fake en prod paper.

---

## Post-cierre (≈00:35–00:45Z)

1. Confirmar sample con `daily_close_at` del día N+1 ancla:

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("paper_telemetry/paper_equity_series.json")
s = json.loads(p.read_text())
closes = [x for x in s["samples"] if x.get("daily_close_at")]
print("hash", s.get("config_hash"))
print("daily_closes", len(closes))
print("last_close", closes[-1] if closes else None)
PY
```

2. Health paper intacto: `curl -sS http://localhost:8000/health/trading-mode | jq .`
3. Digest/action plan (desk): beat `00:45` o `Docs/ops/day*-action-plan-*.md`
4. **No** `docker compose … down -v` · **No** borrar/recrear `paper_telemetry/` · **No** live

---

## Checklist corto día N (copiar a acta)

- [ ] Compose healthy (api/worker/beat + prom/grafana)
- [ ] `effective_mode=paper` · sin `FORCE_REAL_MODE` · `ML_ENABLED=false`
- [ ] `config_hash` freeze invariable
- [ ] Sample con `daily_close_at` para el ancla del día
- [ ] Equity SoT = serie/ledger (no `trades.profit_loss` / dash Rentabilidad)
- [ ] Telemetry intacta (sin wipe)
- [ ] Nota desk: ON_TRACK / AT_RISK + gaps

---

## URLs locales

| Servicio | URL |
|----------|-----|
| API health | http://localhost:8000/health |
| Flower | http://localhost:5555 |
| Grafana | http://localhost:3000 (admin / ver compose) |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |
| Health SRE (tras provision) | Grafana → **GridBot Health SRE (paper)** |

---

## Fallos frecuentes

| Síntoma | Acción |
|---------|--------|
| Script exit 2 “fuera de ventana” | Esperar 23:30Z; no `--write` anticipado |
| `config_hash` raro en host | Ejecutar **solo** en `worker` |
| `daily_close_at` null tras write | Bug I-13 → escalar backend; no inventar mid |
| PipelineHealth WARNING idle | Esperado hasta E4; no reiniciar stack |
| Tentación live / ML | **NO-GO** — regla `40-no-live-without-gate` |
