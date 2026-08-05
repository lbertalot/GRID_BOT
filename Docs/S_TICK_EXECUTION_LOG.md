# S-TICK — Execution log (camino a primer tick paper)

**Repo:** `GRID_BOT`  
**Branch:** `chore/s-tick-c3-first-tick`  
**Rol:** trading-backend-tdd (+ MM freeze C2)  
**Fecha UTC freeze C2:** 2026-08-05T20:46:42Z  
**Fecha UTC primer tick C3:** 2026-08-05T20:50:58Z  
**Modo:** **paper-only** · **No live** · Prohibido `FORCE_REAL_MODE` / órdenes reales

Canónicos: [`PAPER_WINDOW_DAY0.md`](PAPER_WINDOW_DAY0.md) · [`L0_PAPER_FREEZE_PARAMS.md`](L0_PAPER_FREEZE_PARAMS.md) · [`product/DAY0_ACCEPTANCE.md`](product/DAY0_ACCEPTANCE.md) · [`ops/paper-l0-config-freeze.md`](ops/paper-l0-config-freeze.md)

Parámetros MM (sin reset de ventana — **no se tocan**): spacing **100 bps**, desplegado **USD 200**, 10×USD 20, rango ±5%, ETHUSDT.

---

## 0. Veredicto go/no-go

| Veredicto | Valor |
|-----------|--------|
| **C2 — Freeze L0 + `GRID_CONFIG_HASH`** | **GO** |
| **C3 — Primer tick paper (equity MtM)** | **GO** — ≥1 sample serie + ledger con hash freeze |
| **Día 0 de ventana (`L0_DAY0_WINDOW_GO`)** | **NO-GO** |
| Live | **fuera de alcance** — no autorizado |

**Por qué NO-GO día 0 (negocio / [`DAY0_ACCEPTANCE.md`](product/DAY0_ACCEPTANCE.md) §3):**

| AC negocio | Estado | Gap |
|------------|--------|-----|
| B2 freeze A1 | PASS | hash `630abf63…` · `PAPER_FROZEN` |
| B3 params 200 / 100 bps | PASS | intactos |
| B4 ≥1 tick válido (T1–T10) | PASS parcial | tick MtM OK; sin fills aún (fees/slip=0 coherentes) |
| **B5 cierre diario 00:00 UTC ±30 min / `E_0`** | **FAIL** (path Opción B listo) | samples aún `daily_close_at=null`; script §8 — ventana 23:30–00:30Z |
| B10 acta Desk Lead + MM | FAIL | sin firma dual día 0 |
| B11 sin claim edge / PROMOTE_LIVE | PASS | este log no emite edge ni live |

**Blockers día 0 restantes:** cierre diario anclado (`E_0`) + firma dual Desk Lead/MM. No forzar GO.

**Acta freeze A1 (C2):**

| Campo | Valor |
|-------|--------|
| UTC | **2026-08-05T20:46:42Z** |
| mid ETHUSDT (Binance público) | **1923.08000000** |
| min / max (±5%) | 1826.92 / 2019.23 |
| qty (20/mid) | 0.010399 |
| `config_hash` (sidecar) | `630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f` |
| status | `PAPER_FROZEN` |
| spacing / deployed / levels | 100 bps · USD 200 · 10×20 |

**Acta primer tick (C3):**

| Campo | Valor |
|-------|--------|
| UTC | **2026-08-05T20:50:58.565410+00:00** |
| mid ETH feed (marcación) | **1920.81** USDT (ticker real; sin hardcode) |
| path | `compute_paper_portfolio_value` (mismo path que Celery `capture_portfolio_snapshot`) |
| `config_hash` sample | `630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f` (= sidecar) |
| `deployed_capital` | **200** |
| equity / cash / inventory | 1000 / 1000 / 0 (cash paper inicial; sin fills) |
| fees / slippage | campos presentes (`0` / `0`); `PaperCostModel` 24 bps RT |
| reconciliación A3 | **0%** |
| `daily_close_at` | **null** (fuera de ventana ±30 min 00:00 UTC) |

---

## 1. Pasos hechos (evidencia)

### 1.1 C1 — stack paper (previo)

| # | Paso | Resultado |
|---|------|-----------|
| H1 | Stack `docker compose -f docker-compose.local.yml` | Up / healthy |
| H2 | Health trading mode | **`effective_mode=paper`** |
| H3 | Breakers | `any_open=false` |
| H4 | Observabilidad | metrics/prom/grafana/flower 200 |
| H5 | Env host paper-safe | `PAPER_TRADING=true`, `TRADING_ENABLED=false`, `FORCE_REAL_MODE=` vacío |
| H6 | Compose L0 mounts | `GRID_CONFIG_FILE=grid_config_paper_l0.json` + `paper_telemetry` |

### 1.2 C2 — freeze `--write` + hash runtime (2026-08-05)

| # | Paso | Resultado | Evidencia |
|---|------|-----------|-----------|
| C2-1 | Mid ETH público (sin keys) | **1923.08000000** | `GET https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT` |
| C2-2 | `freeze_paper_l0_config.py --mid … --write` | OK | `grid_config_paper_l0.json` → `PAPER_FROZEN`; sidecar `.hash` |
| C2-3 | `GRID_CONFIG_HASH` en `.env` local | Inyectado (NO commit) | igual a sidecar 64 hex |
| C2-4 | Recreate api/worker/beat | force-recreate | compose local |
| C2-5 | Runtime lee freeze | Verificado | `resolve_grid_config_hash()` = sidecar |

### 1.3 C3 — primer tick equity MtM (2026-08-05T20:50:58Z)

| # | Paso | Resultado | Evidencia |
|---|------|-----------|-----------|
| C3-1 | Precondición hash runtime | PASS | `GRID_CONFIG_HASH` = sidecar en api/worker |
| C3-2 | Feed mid real ETHUSDT | **1920.81** | `get_mark_price_feed().get_price("ETHUSDT")` |
| C3-3 | Tick MtM paper | OK | `compute_paper_portfolio_value()` en worker (path S10 / Celery snapshot) |
| C3-4 | Serie | 1 sample | host `paper_telemetry/paper_equity_series.json` (gitignored) |
| C3-5 | Ledger | fees/slippage + cost_model | host `paper_telemetry/paper_equity_ledger.json` (gitignored) |
| C3-6 | Código | autosave ledger en MtM | `app/core/paper_equity_ledger.py` + test C3 |
| C3-7 | Breakers post-tick | `any_open=false` | `GET /api/breakers/status` |

**Queries / inspección local:**

```bash
# Serie (sample C3)
python3.11 -c 'import json; s=json.load(open("paper_telemetry/paper_equity_series.json")); print(s["samples"][-1])'
# → config_hash=630abf63… deployed_capital=200 daily_close_at=None

# Ledger (fees/slippage presentes)
python3.11 -c 'import json; l=json.load(open("paper_telemetry/paper_equity_ledger.json")); print({k:l[k] for k in ("deployed_capital","fees_total_usdt","slippage_total_usdt","cost_model")})'
# → deployed=200 fees=0 slip=0 cost_model 10+2 bps

# Hash freeze
cat grid_config_paper_l0.hash
# → 630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f
```

**No** se activó live / `FORCE_REAL_MODE`.

---

## 2. Freeze — comandos exactos (C2)

### 2.1 Mid público

```bash
curl -sf 'https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT'
# → {"symbol":"ETHUSDT","price":"1923.08000000"}
```

### 2.2 Persistencia `--write`

```bash
cd GRID_BOT
MID=$(curl -sf 'https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT' \
  | python3.11 -c 'import sys,json; print(json.load(sys.stdin)["price"])')
python3.11 scripts/freeze_paper_l0_config.py --mid "$MID" --write
cat grid_config_paper_l0.hash
# → 630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f
```

### 2.3 Inyección runtime (local only)

```bash
# En .env local (NO commit):
GRID_CONFIG_HASH=630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f
docker compose -f docker-compose.local.yml up -d --force-recreate api worker beat
```

### 2.4 Primer tick (C3) — path existente

```bash
docker compose -f docker-compose.local.yml exec -T worker python - <<'PY'
from app.core.paper_equity_ledger import (
    compute_paper_portfolio_value, get_mark_price_feed,
    get_paper_ledger, get_paper_equity_series, reset_paper_telemetry,
)
reset_paper_telemetry()
mid = get_mark_price_feed().get_price("ETHUSDT")
payload = compute_paper_portfolio_value()  # también vía Celery capture_portfolio_snapshot
print(mid, payload, get_paper_equity_series().samples[-1])
print(get_paper_ledger().to_dict()["fees_total_usdt"],
      get_paper_ledger().to_dict()["slippage_total_usdt"])
PY
```

Equivalente Celery (mismo path interno):

```bash
docker compose -f docker-compose.local.yml exec -T worker \
  celery -A app.core.celery_app call \
  app.services.portfolio_snapshot_service.capture_portfolio_snapshot
```

---

## 3. Checklist ejecutable — día 0

Leyenda: `[x]` hecho · `[ ]` pendiente · `[!]` blocker  
Alineado a [`DAY0_ACCEPTANCE.md`](product/DAY0_ACCEPTANCE.md) §3 (B1–B11).

### 3.1 Stack paper-safe (negocio B1 / B8)

- [x] Compose local arriba (`docker-compose.local.yml`)
- [x] `effective_mode=paper` en `/health` y `/health/trading-mode`
- [x] `FORCE_REAL_MODE` vacío; `PAPER_TRADING=true`; `TRADING_ENABLED=false`
- [x] Breakers `any_open=false`
- [x] Metrics / Prometheus / Grafana / Flower respondiendo
- [x] Recreate api/worker/beat **después** de freeze + `GRID_CONFIG_HASH`
- [x] Contenedor: `GRID_CONFIG_FILE=grid_config_paper_l0.json`
- [x] Contenedor: `GRID_CONFIG_HASH` = sidecar
- [x] `ls /app/paper_telemetry` montado (host `./paper_telemetry`)

### 3.2 Freeze A1 (negocio B2 / B3)

- [x] Dry-run freeze con mid público Binance (C1)
- [x] `--write` ejecutado (C2) — owner MM
- [x] `grid_config_paper_l0.hash` versionado en repo
- [x] `GRID_CONFIG_HASH` en runtime **igual** al sidecar (mitiga B1 técnico)
- [x] Acta: hash + mid + timestamp UTC en este log
- [x] Params: ETHUSDT · USD 200 · 10×20 · 100 bps · ±5% · IC-1/IC-2 metadata

### 3.3 Primer tick válido (DoD `L0_PAPER_FREEZE_PARAMS` §3 / negocio B4) — **C3**

- [x] Feed mid ticker real (sin hardcode) al marcar equity
- [x] Ledger path: `paper_telemetry/paper_equity_ledger.json` + `paper_equity_series.json`
- [x] Sample con `deployed_capital=200`, `config_hash` = sidecar, cost_model 24 bps RT
- [x] Fees/slippage campos presentes en ledger (`fees_total_usdt`, `slippage_total_usdt`)
- [x] Reconciliación A3 ≤ 0,1% (0% en tick cash-only)
- [x] Breakers cerrados / IC-1·IC-2 flags en metadata freeze
- [ ] Cierre diario 00:00 UTC (±30 min) para anclar `E_0` → **blocker B5 negocio**

### 3.4 Declarar día 0 de ventana (negocio B5 / B10 / B11)

- [ ] Freeze cerrado + ≥1 tick válido + **cierre diario**
- [ ] Veredicto `L0_DAY0_WINDOW_GO` firmado Desk Lead + MM
- [x] Copy sin claim de rentabilidad / sin `PROMOTE_LIVE`
- [ ] Calendario: `go_live_candidate = inicio + 31d` (contingencia 2026-09-22 si atrasa)

---

## 4. Blockers

| ID | Severidad | Estado | Notas |
|----|-----------|--------|-------|
| **B1** (hash runtime) | Alta | **Cerrado (C2)** | `GRID_CONFIG_HASH` explícito = sidecar |
| **B2** (compose L0) | Alta | **Cerrado (C1)** | `GRID_CONFIG_FILE` + volume |
| **B3** (telemetry volume) | Alta | **Cerrado (C1)** | `./paper_telemetry` montado |
| **B4** (freeze --write) | Media | **Cerrado (C2)** | `PAPER_FROZEN` |
| **B5** (tick E2E) | Media | **Cerrado (C3)** | sample serie + ledger con hash freeze |
| **B6** (IC simulacro) | Baja | Abierto | desk A5 ~2026-08-20; no bloquea C3 |
| **D0-CLOSE** | Alta (día 0) | **Abierto** (path Opción B listo) | esperar 23:30–00:30Z + `capture_paper_e0_daily_close.py --write` o Celery (§8) |
| **D0-SIGNOFF** | Alta (día 0) | **Abierto** | firma dual Desk Lead + MM |

Breakers: **no** blocker (`any_open=false` post-tick).

---

## 5. URLs locales (defaults)

| Servicio | URL |
|----------|-----|
| API / health | http://localhost:8000/health |
| Trading mode | http://localhost:8000/health/trading-mode → **paper** |
| Breakers | http://localhost:8000/api/breakers/status |
| Metrics | http://localhost:8000/metrics |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Flower | http://localhost:5555 |

---

## 6. Coordinación market-maker

Params freeze — **no cambiar sin documentar reset de ventana**:

| Parámetro | Valor congelado |
|-----------|-----------------|
| Spacing | **100 bps** |
| Desplegado | **USD 200** |
| Niveles | 10 × USD 20 |
| Rango | ±5% del mid **1923.08** |
| Símbolo | ETHUSDT only |
| Costos modelo | 24 bps RT (10+2 / lado) |
| `config_hash` | `630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f` |

---

## 7. Prohibido (recordatorio)

- Live / `FORCE_REAL_MODE=true` / órdenes Binance reales
- Commitear secrets o `.env` (el hash sí puede ir en este log / artefactos versionados)
- Bajar spacing “para ciclos” o wipe `./data` / `paper_telemetry` tras arrancar la serie
- Declarar día 0 sin tick válido + cierre diario
- Claim de edge / `PROMOTE_LIVE` en acta día 0 ([`DAY0_ACCEPTANCE.md`](product/DAY0_ACCEPTANCE.md) §0 / §4)

**Paper-only. Este log no autoriza live.**

---

## 8. WS-2 — B5 E_0 path + B9 pnl_mtd honesto + legacy (2026-08-05T21:30Z)

**Rol:** `trading-backend-tdd` · **Modo:** paper-only · **Sin** `FORCE_REAL_MODE` / wipe serie / mid inventado · hash freeze **intact** `630abf63…`

### 8.1 B9 — `pnl_mtd` honesto (CEO-5 / N9)

| Antes | Después |
|-------|---------|
| `status=stale` `value="0"` con ticks cash-only flat (sin E_0) | `status=unavailable` `value=null` + reason ancla usable |

**Fix:** `app/core/pnl_ledger.py` exige ancla MTD = sample pre-mes **o** primer `daily_close_at` (E_0). Ticks intradiarios solos → `PnlUnavailableError`.

**Curl post-fix (docker api):**

```json
{
  "status": "unavailable",
  "value": null,
  "reason": "serie MtM sin ancla usable del mes (falta E_0 / cierre diario 00:00 UTC o sample previo al mes)",
  "source": "app.core.pnl_ledger (B4/MtM-paper)",
  "unit": "usd"
}
```

Tests: `tests/test_pnl_ledger.py` (+ never-zero / E_0 anchor) · `tests/test_e0_daily_close_path.py`.

### 8.2 B5 — Opción B path E_0 (sin inventar mid)

Script: `scripts/capture_paper_e0_daily_close.py`

- Solo escribe si UTC ∈ ±30 min de 00:00 (`daily_close_anchor`).
- Path = `compute_paper_portfolio_value()` + feed real (fail-closed si no hay mid).
- Append-only a serie; **no** wipe; **no** toca freeze hash.

**Estado al cierre WS-2:** fuera de ventana (~21:30Z). Próxima: **2026-08-05T23:30Z → 2026-08-06T00:30Z**.

```bash
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/capture_paper_e0_daily_close.py --dry-run

# En ventana (±30m 00:00 UTC):
docker compose -f docker-compose.local.yml exec -T worker \
  python scripts/capture_paper_e0_daily_close.py --write

# Alternativa: Celery beat capture_portfolio_snapshot (900s) en esa ventana
```

Evidencia unitaria `daily_close_at` no null: `tests/test_e0_daily_close_path.py`.

**B5 negocio** sigue **FAIL** hasta sample real en ventana (no se finge E_0).

### 8.3 Legacy positions warning

| Hallazgo | Mitigación |
|----------|------------|
| `paper_trading_state.json` tenía `BNBUSDT` legacy (floats 2025-09) no importado al ledger MtM | `scripts/quarantine_legacy_paper_positions.py --write` → `positions={}` + `_quarantined_positions` |
| SoT | `PaperEquityLedger` — **no** se importó inventario legacy (evitar contaminar E_0) |
| Compose local | mounts `./scripts` + `./paper_trading_state.json` |

`load_state` deja de WARNING si cuarentenado.

### 8.4 Smoke

| Check | Resultado |
|-------|-----------|
| `effective_mode` health + CEO | **paper** |
| `pnl_mtd` | **unavailable / null** |
| breakers | `ok` / lista vacía |
| `FORCE_REAL_MODE` | vacío |

**Día 0:** `L0_DAY0_WINDOW_GO` sigue **NO-GO** (B5 E_0 runtime + B10 firmas). Sin claim edge / sin `PROMOTE_LIVE`.

---

## Changelog

| Fecha UTC | Cambio | Autor |
|-----------|--------|-------|
| 2026-08-05T19:58:05Z | Smoke stack paper + dry-run freeze mid 1920.38 + checklist + blockers B1–B6; compose L0/telemetry | trading-devops |
| 2026-08-05T20:46:42Z | **C2** freeze `--write` mid 1923.08 · hash `630abf63…` · `GRID_CONFIG_HASH` local · recreate | trader-market-maker |
| 2026-08-05T20:50:58Z | **C3** primer tick MtM · sample serie+ledger · B5 técnico cerrado · `L0_DAY0_WINDOW_GO=NO-GO` (falta cierre diario + firmas) | trading-backend-tdd |
| 2026-08-05T21:30Z | **WS-2** pnl_mtd unavailable honesto; script E_0 Opción B; quarantine legacy BNB; compose mounts scripts+legacy state | trading-backend-tdd |

