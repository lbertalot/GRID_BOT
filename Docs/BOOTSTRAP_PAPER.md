# Bootstrap paper local — GRID_BOT

**Fecha:** 2026-08-05  
**Branch:** `main` (post kickoff S1–S13 + PR #46)  
**Modo:** paper-first · **No es go-live** (gate objetivo 2026-09-15)

Runbook para levantar el stack Docker local funcional con los cambios actuales, sin secrets reales ni órdenes live.

---

## 1. Prerrequisitos

- Docker + Compose v2+
- Puerto libres por defecto: `8000`, `5432`, `6379`, `3000`, `9090`, `5555`, `9093`
- Repo: `GRID_BOT/` en `main` al día con `origin`

## 2. Levantar

```bash
cd GRID_BOT
git checkout main && git pull --ff-only

cp env.example .env
# Obligatorio: SECRET_KEY local (no commitear .env)
openssl rand -hex 32   # pegar en SECRET_KEY=
# API_KEY local (Bearer para CEO/ops/books)
# PAPER_TRADING=true
# TRADING_ENABLED=false
# FORCE_REAL_MODE=   (vacío)
# BINANCE_* vacíos o placeholders — nunca keys de prod

docker compose -f docker-compose.local.yml up --build -d
```

Conflicto de puertos (otro stack ya corriendo):

```bash
GRIDBOT_PREFIX=gridbot_paper API_PORT=8010 DB_PORT=5442 REDIS_PORT=6389 \
FLOWER_PORT=5565 PROMETHEUS_PORT=9190 ALERTMANAGER_PORT=9193 GRAFANA_PORT=3010 \
docker compose -f docker-compose.local.yml -p gridbot_paper up -d
```

Bajar / reset:

```bash
docker compose -f docker-compose.local.yml down          # para servicios
docker compose -f docker-compose.local.yml down -v       # + borra volúmenes DB/Redis
```

El servicio `migrate` corre `alembic upgrade head` una vez antes de `api`/`worker`/`beat`.

## 3. URLs locales (defaults)

| Servicio | URL | Credenciales |
|----------|-----|----------------|
| API | http://localhost:8000 | Bearer `API_KEY` del `.env` |
| Health | http://localhost:8000/health | público |
| Trading mode | http://localhost:8000/health/trading-mode | público |
| CEO dashboard HTML | http://localhost:8000/api/ceo/dashboard | Bearer |
| CEO overview JSON | http://localhost:8000/api/ceo/overview | Bearer |
| Capital risk | http://localhost:8000/api/risk/capital-status | público read-only |
| Ops summary | http://localhost:8000/api/ops/summary | público |
| Capital books | http://localhost:8000/api/capital/books | Bearer (según router) |
| Breakers | http://localhost:8000/api/breakers/status | público |
| Metrics | http://localhost:8000/metrics | Prometheus scrape |
| Grafana | http://localhost:3000 | `admin` / `gridbot123` |
| Prometheus | http://localhost:9090 | — |
| Flower | http://localhost:5555 | `admin` / `admin` |

## 4. Flags de modo (qué significan)

| Variable | Valor paper bootstrap | Nota |
|----------|----------------------|------|
| `PAPER_TRADING` | `true` | Simula fills; ledger paper es SoT de equity |
| `TRADING_ENABLED` | `false` | Compose fail-closed `:-false`; **B26 cerrado (S-GATE):** corta órdenes reales vía `assert_real_order_allowed` |
| `FORCE_REAL_MODE` | vacío / false | **Prohibido** `true` sin gate humano + firma dual |
| `EMERGENCY_STOP` | `false` | **B26 cerrado (S-GATE):** `true` → `RealOrderBlocked` en path de ejecución |
| `KILL_BASIS` | `trading` | Kill sobre capital tradable (aportado − ops), Amendment 01 |
| `BINANCE_TESTNET` | `false` | Paper no requiere exchange; evitar mainnet keys |

`effective_mode` esperado: **`paper`** (y `live_gate_signed=false`).

## 5. Smoke checklist (copy-paste)

```bash
export API_KEY='…tu API_KEY local…'
export AUTH="Authorization: Bearer $API_KEY"

curl -sf http://localhost:8000/health | jq .
curl -sf http://localhost:8000/health/trading-mode | jq .trading.effective_mode
# → "paper"

curl -sf http://localhost:8000/api/risk/capital-status | jq '.data.kill_basis,.data.severity'
curl -sf -H "$AUTH" http://localhost:8000/api/ceo/overview | jq '.effective_mode,.equity_reconciled.status,.ops_burn_mtd.status'
curl -sf http://localhost:8000/api/ops/summary | jq '.ops_reserve_remaining,.ops_burn_mtd'
curl -sf -H "$AUTH" http://localhost:8000/api/capital/books | jq '.books[].book_id'
curl -sf http://localhost:8000/api/breakers/status | jq '.any_open'
curl -sf -o /dev/null -w '%{http_code}\n' -H "$AUTH" http://localhost:8000/api/ceo/dashboard
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:8000/metrics
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:3000/login
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:9090/-/healthy
curl -sf -o /dev/null -w '%{http_code}\n' -u admin:admin http://localhost:5555/

# Observabilidad: cAdvisor no "healthy pero vacío" (ver Docs/ops/silent-failures-checklist.md)
make smoke-observability
# o copy-paste:
curl -sf http://localhost:8081/api/v1.3/docker | jq 'length'   # > 0
curl -sf 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22cadvisor%22%7D' \
  | jq -e '.data.result[0].value[1] == "1"'
curl -sf 'http://localhost:9090/api/v1/query?query=count(container_cpu_usage_seconds_total%7Bid!%3D%22%2F%22%7D)' \
  | jq -e '(.data.result[0].value[1] | tonumber) >= 1'

docker exec gridbot_api alembic current
# → head (ej. 20260505_mc_backtest_fk)
```

Esperado día-1: health OK, `effective_mode=paper`, capital/ops/books/breakers 200, CEO overview con cards capital/ops en `ok` o `stale` (no 500), Grafana/Prometheus/Flower up, cadvisor con discovery Docker y series `container_*` por contenedor (`id!="/"`).

## 6. Known issues vs blockers pre-live

Fuente: [`pre-live-blockers.md`](pre-live-blockers.md).

| ID | Afecta paper day-1? | Notas |
|----|---------------------|-------|
| B1 | Parcial | Breakers API vs worker no compartidos; en paper el badge puede mentir bajo carga |
| B14 | Sí (métricas) | Varios simuladores; SoT de equity = `PaperEquityLedger` (S10) |
| B15 | Mitigado (S-GATE) | Guard en path de órdenes; live sigue exigiendo firma dual |
| B19 | Mitigado local | `./data` montado en compose local; en Heroku sí es efímero |
| B22 / B23 | Negocio | Ops vs PnL / techo mensual — decisión CEO, no bloquea stack |
| B26 | Mitigado (S-GATE) | Env kill-switch corta órdenes reales; ver `Docs/LIVE_CHECKLIST.md` |
| B27 | Mitigado (S-PAPER-ISO) | CommissionManager paper-iso; keys vacías siguen siendo buena higiene |
| pnl_mtd CEO | Sí (UI) | Sin `pnl_ledger` → card `unavailable` (esperado hasta ADR-004 PnL) |

## 7. Seguridad runtime (checklist)

- [ ] `.env` en `.gitignore` / no commiteado
- [ ] Sin `BINANCE_*` de producción
- [ ] `FORCE_REAL_MODE` vacío
- [ ] CEO overview exige Bearer salvo `CEO_DASHBOARD_PUBLIC=true` (no activar en host expuesto)
- [ ] Logs: no deben mostrar API keys en claro (redaction S11)

## 8. Próximo paso (no live)

1. **Freeze de config paper** + arrancar tick / ventana paper (desk-policy L0).
2. Generar serie de equity MtM (`PaperEquityLedger`) para tear-sheet (`trading-pnl-tear-sheet`).
3. Cerrar gaps B26/B27/B15 **antes** de cualquier conversación de firma live (2026-09-15).
4. No sugerir `FORCE_REAL_MODE` ni Heroku live desde este runbook.

## 9. Veredicto desk (plantilla)

Tras el smoke de §5:

- **PAPER_STACK_READY** — compose healthy, `effective_mode=paper`, endpoints capital/ops/CEO OK, sin secrets reales.
- o **GAPS** con owner (ej. B27 keys vacías obligatorias; wiring PnL MTD).
