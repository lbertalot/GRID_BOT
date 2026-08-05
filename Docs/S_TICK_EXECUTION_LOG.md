# S-TICK — Execution log (camino a primer tick paper)

**Repo:** `GRID_BOT`  
**Branch:** `docs/s-tick-execution-log`  
**Rol:** trading-devops  
**Fecha UTC del smoke:** 2026-08-05T19:58:05Z  
**Modo:** **paper-only** · **No live** · Prohibido `FORCE_REAL_MODE` / órdenes reales

Canónicos: [`PAPER_WINDOW_DAY0.md`](PAPER_WINDOW_DAY0.md) · [`L0_PAPER_FREEZE_PARAMS.md`](L0_PAPER_FREEZE_PARAMS.md) · [`ops/paper-l0-config-freeze.md`](ops/paper-l0-config-freeze.md)

Parámetros MM (sin reset de ventana — **no se tocan**): spacing **100 bps**, desplegado **USD 200**, 10×USD 20, ± ±5%, ETHUSDT.

---

## 0. Veredicto go/no-go — declarar día 0 esta semana

| Veredicto | Valor |
|-----------|--------|
| **Día 0 de ventana (L0_DAY0_WINDOW_GO)** | **NO-GO** |
| **Camino operativo a freeze + primer tick (S-TICK prep)** | **GO condicional** esta semana si se cierran blockers §4 |
| Target freeze ideal | ≤ 2026-08-15 00:00 UTC (desk C3) |
| Live | **fuera de alcance** — no autorizado |

**Por qué NO-GO día 0 ahora:** config aún `PAPER_FREEZE_CANDIDATE` (sin `--write`); no hay `grid_config_paper_l0.hash` persistido; no hay sample en `PaperEquitySeries` con `config_hash` congelado; `GRID_CONFIG_HASH` no inyectado en runtime; telemetría paper sin volumen montado hasta este PR.

---

## 1. Pasos hechos (evidencia 2026-08-05)

| # | Paso | Resultado | Evidencia |
|---|------|-----------|-----------|
| H1 | Stack `docker compose -f docker-compose.local.yml` | Up / healthy (api, worker, beat, db, redis, prom, grafana, flower, alertmanager, …) | `docker compose … ps` — api Up healthy |
| H2 | Health trading mode | **`effective_mode=paper`** | `GET /health/trading-mode` → `paper_trading=true`, `force_real_mode=false`, `trading_enabled=false`, `live_gate_signed=false` |
| H3 | Breakers | **ninguno abierto** | `GET /api/breakers/status` → `any_open=false`, `open_count=0` |
| H4 | Observabilidad | metrics/prom/grafana/flower **200** | `curl` locales :8000/metrics, :9090, :3000, :5555 |
| H5 | Env host paper-safe | `PAPER_TRADING=true`, `TRADING_ENABLED=false`, `FORCE_REAL_MODE=` vacío, `EMERGENCY_STOP=false` | `.env` local (no secretos en este log) |
| H6 | Params freeze candidato | spacing 100 · investment 200 · notional/nivel 20 · grids 10 · IC-1/IC-2 en metadata | `grid_config_paper_l0.json` status `PAPER_FREEZE_CANDIDATE` |
| H7 | Mid ETH público (sin keys) | **1920.38** USDT | `GET https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT` (también data-api.binance.vision) |
| H8 | Freeze **dry-run** (sin `--write`) | OK — no persistió artefactos | Ver §2 |
| H9 | Compose mínimo S-TICK | `GRID_CONFIG_FILE` + volumen `paper_telemetry` + mount L0 json | este PR |

**No ejecutado a propósito:** `freeze … --write` (evita congelar mid volátil antes de acta desk / reinicio de ventana). **No** se activó live.

---

## 2. Freeze dry-run — comando exacto

### 2.1 Obtener mid (público, sin API keys)

```bash
curl -sf 'https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT'
# → {"symbol":"ETHUSDT","price":"1920.38000000"}
```

Fallback mirror:

```bash
curl -sf 'https://data-api.binance.vision/api/v3/ticker/price?symbol=ETHUSDT'
```

Si la red falla: usar placeholder `<MID>` y repetir el fetch el día del freeze real.

### 2.2 Dry-run (corrido 2026-08-05)

```bash
cd GRID_BOT
python3.11 scripts/freeze_paper_l0_config.py --mid 1920.38
```

Salida observada:

```
mid=1920.38000000 min=1824.36 max=2016.39 qty=0.010414
config_hash=74d089808874b95d06af52201842e440d6b28f1dd5fc29372f7b6f932e24f47d
per_level_usd=20.0 levels=10 spacing_bps=100
(dry-run; pass --write to persist)
```

| Campo | Valor dry-run |
|-------|----------------|
| mid | 1920.38 |
| min (−5%) | 1824.36 |
| max (+5%) | 2016.39 |
| qty (20/mid) | 0.010414 |
| spacing_bps | 100 |
| levels × notional | 10 × 20 |
| `config_hash` (sidecar algoritmo freeze) | `74d089808874b95d06af52201842e440d6b28f1dd5fc29372f7b6f932e24f47d` |

**Nota:** este hash es del dry-run con mid 1920.38. El día del freeze real el mid (y por tanto el hash) **cambiará**. No reutilizar este hash como A1 definitivo.

### 2.3 Persistencia (pendiente — día del freeze)

```bash
# Solo cuando Desk Lead + MM acuerden abrir la ventana (reinicia reloj A1):
MID=$(curl -sf 'https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT' \
  | python3.11 -c 'import sys,json; print(json.load(sys.stdin)["price"])')
python3.11 scripts/freeze_paper_l0_config.py --mid "$MID"          # dry-run final
python3.11 scripts/freeze_paper_l0_config.py --mid "$MID" --write  # persiste json + .hash
cat grid_config_paper_l0.hash
# En .env local (NO commit):
# GRID_CONFIG_HASH=<pegado desde .hash>
docker compose -f docker-compose.local.yml up -d --force-recreate api worker beat
```

Tras `--write`: status → `PAPER_FROZEN`. Cualquier retune de spacing/notional/rango **reinicia la ventana** (documentar reset).

---

## 3. Checklist ejecutable — día 0

Leyenda: `[x]` hecho · `[ ]` pendiente · `[!]` blocker

### 3.1 Stack paper-safe

- [x] Compose local arriba (`docker-compose.local.yml`)
- [x] `effective_mode=paper` en `/health` y `/health/trading-mode`
- [x] `FORCE_REAL_MODE` vacío; `PAPER_TRADING=true`; `TRADING_ENABLED=false`
- [x] Breakers `any_open=false`
- [x] Metrics / Prometheus / Grafana / Flower respondiendo
- [ ] Recreate api/worker/beat **después** de merge de este PR (nuevos mounts + `GRID_CONFIG_FILE`)
- [ ] Confirmar en contenedor: `echo $GRID_CONFIG_FILE` → `grid_config_paper_l0.json`
- [ ] Confirmar `ls -la /app/paper_telemetry` escribible (host `./paper_telemetry`)

### 3.2 Freeze A1

- [x] Dry-run freeze con mid público Binance
- [ ] `--write` acordado (owner: Desk Lead + trader-market-maker)
- [ ] `grid_config_paper_l0.hash` en repo working tree (artefacto local; valorar si se versiona o solo se registra en acta)
- [!] `GRID_CONFIG_HASH` en runtime **igual** al sidecar (ver blocker B1)
- [ ] Acta: hash + mid + timestamp UTC registrados

### 3.3 Primer tick válido (DoD `L0_PAPER_FREEZE_PARAMS` §3)

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

## 4. Blockers abiertos

| ID | Severidad | Blocker | Owner sugerido | Mitigación |
|----|-----------|---------|----------------|------------|
| **B1** | Alta | `resolve_grid_config_hash()` sin `GRID_CONFIG_HASH` hashea el JSON completo (`compute_config_hash`); el script freeze usa subset → **hashes distintos**. Sin env explícito, A1 no cierra contra sidecar. | devops + backend | Tras `--write`: `GRID_CONFIG_HASH=$(cat grid_config_paper_l0.hash)` en `.env` local; recreate api/worker/beat |
| **B2** | Alta | Antes de este PR: compose montaba solo `grid_config_optimized.json`; runtime hasheaba optimized (`1da62476…`) ≠ L0 | devops | Fix en este PR: `GRID_CONFIG_FILE=grid_config_paper_l0.json` + volume |
| **B3** | Alta | `paper_telemetry/` no persistía en host (dir ausente en contenedor) | devops | Volume `./paper_telemetry:/app/paper_telemetry` + `.gitkeep` |
| **B4** | Media | Freeze `--write` aún no corrido → status `PAPER_FREEZE_CANDIDATE`, mid/qty null | desk / MM | Ejecutar §2.3 el día acordado (ideal ≤ 2026-08-15) |
| **B5** | Media | Primer tick / wiring grid→`PaperEquityLedger` no verificado end-to-end en este smoke | backend + MM | Smoke tick paper tras freeze; no contar jornadas previas |
| **B6** | Baja | IC-1/IC-2 simulacro desk A5 (deadline ~2026-08-20) — no bloquea prep freeze; sí A7 de ventana completa | risk / MM | Planificar post día 0 |

Breakers: **no** son blocker hoy (`any_open=false`).

---

## 5. URLs locales (defaults verificados)

| Servicio | URL |
|----------|-----|
| API / health | http://localhost:8000/health |
| Trading mode | http://localhost:8000/health/trading-mode → **paper** |
| Breakers | http://localhost:8000/api/breakers/status |
| Metrics | http://localhost:8000/metrics |
| Grafana | http://localhost:3000 (`admin` / `gridbot123`) |
| Prometheus | http://localhost:9090 |
| Flower | http://localhost:5555 (`admin` / `admin`) |
| Alertmanager | http://localhost:9093 |

---

## 6. Coordinación market-maker

Params freeze alineados a desk / MM — **no cambiar sin documentar reset de ventana**:

| Parámetro | Valor congelable |
|-----------|------------------|
| Spacing | **100 bps** |
| Desplegado | **USD 200** |
| Niveles | 10 × USD 20 |
| Rango | ±5% del mid de freeze |
| Símbolo | ETHUSDT only |
| Costos modelo | 24 bps RT (10+2 / lado) |

Cualquier edit de `grid_config_paper_l0.json` post-`PAPER_FROZEN` → **reinicio de ventana** + nuevo hash + nueva acta.

---

## 7. Prohibido (recordatorio)

- Live / `FORCE_REAL_MODE=true` / órdenes Binance reales
- Commitear secrets o `GRID_CONFIG_HASH` de prod
- Bajar spacing “para ciclos” o wipe `./data` / `paper_telemetry` tras arrancar la serie
- Declarar día 0 sin tick válido + cierre diario

**Paper-only. Este log no autoriza live.**

---

## Changelog

| Fecha UTC | Cambio | Autor |
|-----------|--------|-------|
| 2026-08-05 | Smoke stack paper + dry-run freeze mid 1920.38 + checklist + blockers B1–B6; compose L0/telemetry | trading-devops |
