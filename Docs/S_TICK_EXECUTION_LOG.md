# S-TICK — Execution log (camino a primer tick paper)

**Repo:** `GRID_BOT`  
**Branch:** `chore/s-tick-c2-freeze`  
**Rol:** trader-market-maker (+ devops ops)  
**Fecha UTC C1 recreate+smoke:** 2026-08-05T20:42:26Z  
**Fecha UTC freeze C2:** 2026-08-05T20:46:42Z  
**Modo:** **paper-only** · **No live** · Prohibido `FORCE_REAL_MODE` / órdenes reales

Canónicos: [`PAPER_WINDOW_DAY0.md`](PAPER_WINDOW_DAY0.md) · [`L0_PAPER_FREEZE_PARAMS.md`](L0_PAPER_FREEZE_PARAMS.md) · [`ops/paper-l0-config-freeze.md`](ops/paper-l0-config-freeze.md)

Parámetros MM (sin reset de ventana — **no se tocan**): spacing **100 bps**, desplegado **USD 200**, 10×USD 20, rango ±5%, ETHUSDT.

---

## 0. Veredicto go/no-go

| Veredicto | Valor |
|-----------|--------|
| **C1 stack paper + smokes** | **GO** (2026-08-05T20:42Z) |
| **C2 — Freeze L0 + `GRID_CONFIG_HASH`** | **GO** |
| **C3 — Primer tick paper** | **GO** (precondiciones C2 cerradas; falta smoke tick + sample serie) |
| **Día 0 de ventana (L0_DAY0_WINDOW_GO)** | **NO-GO** (falta tick válido + cierre diario 00:00 UTC) |
| Live | **fuera de alcance** — no autorizado |

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

---

## 1. Pasos hechos (evidencia)

### 1.1 C1 — stack paper + smokes (2026-08-05T20:42Z)

```bash
docker compose -f docker-compose.local.yml up -d --build --force-recreate
# Volume: grid_bot_ops_ledger_data · api healthy ~20:42:03Z
```

| Check | Resultado | Timestamp / nota |
|-------|-----------|------------------|
| Volume `ops_ledger_data` | **OK** → `/var/lib/gridbot/ops` | recreate C1 |
| Mount L0 + `paper_telemetry` | **OK** | api/worker/beat |
| Env runtime | `GRID_CONFIG_FILE`, `PAPER_TELEMETRY_DIR`, `OPS_LEDGER_PATH` | paper-safe |
| `GET /health` / trading-mode | `effective_mode=paper`, `force_real_mode=false` | 20:42:26Z |
| `GET /api/breakers/status` | `any_open=false` | 20:42:27Z |
| cadvisor | healthy; **12** containers | Docker Desktop OK |
| `make smoke-observability` | **PASS** (3/3) | 20:42:38Z |

### 1.2 C2 — freeze `--write` + hash runtime (2026-08-05)

| # | Paso | Resultado | Evidencia |
|---|------|-----------|-----------|
| C2-1 | Mid ETH público (sin keys) | **1923.08000000** | `GET https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT` |
| C2-2 | `freeze_paper_l0_config.py --mid … --write` | OK | `grid_config_paper_l0.json` → `PAPER_FROZEN`; sidecar `.hash` |
| C2-3 | `GRID_CONFIG_HASH` en `.env` local | Inyectado (NO commit) | igual a sidecar 64 hex |
| C2-4 | Recreate api/worker/beat | force-recreate | `docker compose -f docker-compose.local.yml up -d --force-recreate api worker beat` |
| C2-5 | Runtime lee freeze | Verificado | env + config montada; params MM intactos |

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

Salida observada:

```
mid=1923.08000000 min=1826.92 max=2019.23 qty=0.010399
config_hash=630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f
per_level_usd=20.0 levels=10 spacing_bps=100
wrote …/grid_config_paper_l0.json
wrote …/grid_config_paper_l0.hash
```

### 2.3 Inyección runtime (local only)

```bash
# En .env local (NO commit):
GRID_CONFIG_HASH=630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f
docker compose -f docker-compose.local.yml up -d --force-recreate api worker beat
```

Cualquier retune de spacing/notional/rango **reinicia la ventana** (nuevo hash + nueva acta).

### 2.4 Dry-run histórico (C1, no A1 definitivo)

Dry-run mid 1920.38 → hash `74d08980…` — **obsoleto**; no usar como firma A1.

---

## 3. Checklist ejecutable — día 0

Leyenda: `[x]` hecho · `[ ]` pendiente · `[!]` blocker

### 3.1 Stack paper-safe

- [x] Compose local arriba (`docker-compose.local.yml`)
- [x] `effective_mode=paper` en `/health` y `/health/trading-mode`
- [x] `FORCE_REAL_MODE` vacío; `PAPER_TRADING=true`; `TRADING_ENABLED=false`
- [x] Breakers `any_open=false`
- [x] Metrics / Prometheus / Grafana / Flower respondiendo
- [x] Recreate api/worker/beat **después** de freeze + `GRID_CONFIG_HASH`
- [x] Contenedor: `GRID_CONFIG_FILE=grid_config_paper_l0.json`
- [x] Contenedor: `GRID_CONFIG_HASH` = sidecar
- [x] `ls /app/paper_telemetry` montado (host `./paper_telemetry`)

### 3.2 Freeze A1

- [x] Dry-run freeze con mid público Binance (C1)
- [x] `--write` ejecutado (C2) — owner MM
- [x] `grid_config_paper_l0.hash` versionado en repo
- [x] `GRID_CONFIG_HASH` en runtime **igual** al sidecar (mitiga B1)
- [x] Acta: hash + mid + timestamp UTC en este log

### 3.3 Primer tick válido (DoD `L0_PAPER_FREEZE_PARAMS` §3) — **C3**

- [ ] Feed mid ticker real (sin hardcode) al marcar equity
- [ ] Ledger path: `paper_telemetry/paper_equity_ledger.json` + `paper_equity_series.json`
- [ ] Sample con `deployed_capital=200`, `config_hash` = sidecar, costos 24 bps RT
- [ ] Reconciliación A3 ≤ 0,1%
- [ ] Breakers cerrados / IC-1·IC-2 no inconsistentes
- [ ] Cierre diario 00:00 UTC (±30 min) para anclar `E_0`

### 3.4 Declarar día 0 de ventana

- [ ] Freeze cerrado + ≥1 tick válido + cierre diario
- [ ] Veredicto `L0_DAY0_WINDOW_GO` firmado Desk Lead + MM
- [ ] Calendario: `go_live_candidate = inicio + 31d` (contingencia 2026-09-22 si atrasa)

---

## 4. Blockers

| ID | Severidad | Estado | Notas |
|----|-----------|--------|-------|
| **B1** | Alta | **Cerrado (C2)** | `GRID_CONFIG_HASH` explícito en `.env` = sidecar; recreate api/worker/beat |
| **B2** | Alta | **Cerrado (C1)** | `GRID_CONFIG_FILE=grid_config_paper_l0.json` + volume |
| **B3** | Alta | **Cerrado (C1)** | Volume `./paper_telemetry:/app/paper_telemetry` |
| **B4** | Media | **Cerrado (C2)** | `--write` → `PAPER_FROZEN`, mid/qty seteados |
| **B5** | Media | **Abierto — C3** | Primer tick / wiring grid→`PaperEquityLedger` E2E |
| **B6** | Baja | Abierto | IC-1/IC-2 simulacro desk A5 (~2026-08-20); no bloquea C3 |

Breakers: **no** blocker (`any_open=false` en C1; re-verificar post-recreate).

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

**Paper-only. Este log no autoriza live.**

---

## Changelog

| Fecha UTC | Cambio | Autor |
|-----------|--------|-------|
| 2026-08-05T19:58:05Z | Smoke stack paper + dry-run freeze mid 1920.38 + checklist + blockers B1–B6; compose L0/telemetry | trading-devops |
| 2026-08-05T20:46:42Z | **C2** freeze `--write` mid 1923.08 · hash `630abf63…` · `GRID_CONFIG_HASH` local · recreate api/worker/beat · GO C3 | trader-market-maker |
