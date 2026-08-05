# S-TICK — Paper window día 0 (freeze)

**Repo:** `GRID_BOT`  
**Fecha del runbook:** 2026-08-05  
**Sprint:** Acta CEO 02 → `S-GATE` → `S-PAPER-ISO` → `S-BREAKERS` → **`S-TICK`**  
**Modo:** paper-first · **No es go-live** · **Prohibido** `FORCE_REAL_MODE` y órdenes live

Fuente de política: monorepo `Docs/squad/desk-policy-l0.md` §2.4 / §6 · Acta `Docs/CEO-ACTA-02-2026-08-05.md` · freeze ops `Docs/ops/paper-l0-config-freeze.md` · bootstrap `Docs/BOOTSTRAP_PAPER.md`.

---

## 0. Calendario

| Hito | Fecha (UTC) | Nota |
|------|-------------|------|
| **Freeze + arranque ventana (ideal)** | **≤ 2026-08-15 00:00** | Desk-policy C3 / A4 — inamovible si se quiere go-live 15/09 |
| Ventana canónica (30 retornos diarios) | 2026-08-15 → 2026-09-14 | Cierre diario 00:00 UTC; `config_hash` invariable |
| Go-live target | 2026-09-15 | Solo con gate dual + B15/B26/B27 verdes |
| **Contingencia go-live** | **2026-09-22** | Pre-aprobada (Acta 02) si la serie paper no cierra a tiempo |

Si el freeze se atrasa, desplazar el go-live en bloque (ej. arranque 22/08 → go-live 22/09). Comunicar el día que se conoce el arranque, no el 14/09.

---

## 1. Recrear compose paper (`docker-compose.local.yml`)

Flags **paper-safe** ya van en el compose (`x-app-env`). No sobreescribirlos a live.

```bash
cd GRID_BOT
git checkout main && git pull --ff-only

cp env.example .env
# SECRET_KEY local (openssl rand -hex 32) — no commitear .env
# API_KEY local para Bearer CEO/ops
# Verificar / dejar:
#   PAPER_TRADING=true
#   TRADING_ENABLED=false
#   FORCE_REAL_MODE=          # vacío
#   EMERGENCY_STOP=false
#   BINANCE_* vacíos o placeholders — nunca keys de prod

docker compose -f docker-compose.local.yml up --build -d
```

Defaults paper en compose (no tocar durante la ventana):

| Variable | Valor paper-safe |
|----------|------------------|
| `PAPER_TRADING` | `true` |
| `TRADING_ENABLED` | `false` |
| `FORCE_REAL_MODE` | `""` (vacío) |
| `EMERGENCY_STOP` | `false` |
| `BINANCE_TESTNET` | `false` (paper no requiere exchange) |

Conflicto de puertos (otro stack ya corriendo):

```bash
GRIDBOT_PREFIX=gridbot_paper API_PORT=8010 DB_PORT=5442 REDIS_PORT=6389 \
FLOWER_PORT=5565 PROMETHEUS_PORT=9190 ALERTMANAGER_PORT=9193 GRAFANA_PORT=3010 \
docker compose -f docker-compose.local.yml -p gridbot_paper up -d
```

Parar / reset (cuidado: `-v` borra DB/Redis y **rompe** la serie si ya arrancó la ventana):

```bash
docker compose -f docker-compose.local.yml down
# Solo día 0 / antes del freeze:
docker compose -f docker-compose.local.yml down -v
```

---

## 2. Checklist freeze (`config_hash`) — qué congelar / qué NO cambiar 30 días

### 2.1 Archivos y artefactos

| Artefacto | Rol |
|-----------|-----|
| `grid_config_paper_l0.json` | Config L0 candidata → tras freeze: `PAPER_FROZEN` |
| `grid_config_paper_l0.hash` | Sidecar SHA-256 tras `--write` |
| `scripts/freeze_paper_l0_config.py` | Fija mid, rango ±5%, qty, escribe hash |
| Ledger S10 / `PaperEquityLedger` | Debe persistir el mismo `config_hash` en cada sample |

### 2.2 Cómo congelar (día 0, antes de ticks)

```bash
# 1) Mid spot ETHUSDT (feed del bot / ticker; mercado puede ser price feed mainnet)
# 2) Dry-run
python3.11 scripts/freeze_paper_l0_config.py --mid <PRECIO>
# 3) Persistir
python3.11 scripts/freeze_paper_l0_config.py --mid <PRECIO> --write
# 4) Registrar hash en el ledger / desk; apuntar el bot a esta config
cat grid_config_paper_l0.hash
```

Parámetros fijos (desk §2.4) — **no negociables** en la ventana:

| Parámetro | Valor |
|-----------|-------|
| Símbolo | ETHUSDT solo |
| Desplegado | USD 200 |
| Niveles | 10 × USD 20 |
| Spacing | 100 bps |
| Rango | ±5% |
| Modo | PAPER (`force_real_mode=false`) |
| IC-1 / IC-2 | Freno fuera de rango / flatten Core a −10% desplegado |

### 2.3 Qué NO cambiar durante 30 días

Cualquier cambio de los siguientes **reinicia la ventana** (desk A1 / N11):

- [ ] `grid_config_paper_l0.json` (mid, min/max, qty, grids, spacing, notional, investment)
- [ ] `grid_config_paper_l0.hash` / `config_hash` efectivo en samples
- [ ] Flags paper-safe del compose / `.env` → **nunca** `FORCE_REAL_MODE=true`, ni `PAPER_TRADING=false` con live
- [ ] Universo (no agregar pares; BTCUSDT permanece inactivo)
- [ ] Modelo de costos / definición de equity MtM del ledger S10
- [ ] `down -v` o wipe de `./data` / ledger una vez arrancada la serie

Permitido sin reinicio: secrets rotados locales, logs, dashboards Grafana, alertas de observabilidad, fixes de infra que no toquen sizing/ejecución/ledger.

Rechazos inmediatos (no correr): spacing &lt; 40 bps · notional/nivel &lt; USD 15.

---

## 3. Health smoke (día 0)

```bash
export API_KEY='…tu API_KEY local…'
export AUTH="Authorization: Bearer $API_KEY"
# Si usás API_PORT=8010, reemplazá :8000 abajo

curl -sf http://localhost:8000/health | jq .
curl -sf http://localhost:8000/health/trading-mode | jq .
# Esperado: trading.effective_mode == "paper"
#           live_gate_signed == false (o equivalente)

curl -sf http://localhost:8000/api/breakers/status | jq '.any_open'
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:8000/metrics
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:9090/-/healthy
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:3000/login
curl -sf -o /dev/null -w '%{http_code}\n' -u admin:admin http://localhost:5555/

docker compose -f docker-compose.local.yml ps
```

Go día 0: health 200, **`effective_mode=paper`**, Prometheus/Grafana/Flower up, `FORCE_REAL_MODE` vacío, hash congelado registrado.

---

## 4. URLs locales (defaults)

| Servicio | URL | Notas |
|----------|-----|-------|
| API | http://localhost:8000 | Bearer `API_KEY` |
| Health | http://localhost:8000/health | público |
| Trading mode | http://localhost:8000/health/trading-mode | debe ser `paper` |
| Metrics | http://localhost:8000/metrics | scrape Prometheus |
| CEO dashboard | http://localhost:8000/api/ceo/dashboard | Bearer |
| CEO overview | http://localhost:8000/api/ceo/overview | Bearer |
| Breakers | http://localhost:8000/api/breakers/status | público |
| Grafana | http://localhost:3000 | `admin` / `gridbot123` |
| Prometheus | http://localhost:9090 | — |
| Alertmanager | http://localhost:9093 | — |
| Flower | http://localhost:5555 | `admin` / `admin` |

Con prefijo paper: API `:8010`, Grafana `:3010`, Prometheus `:9190`, Flower `:5565`, Alertmanager `:9193`.

---

## 5. Contingencia 22/09

Si la serie de 30 retornos **no cierra** a tiempo para el gate del 2026-09-15:

1. **No improvisar live.** Mantener paper; no activar `FORCE_REAL_MODE`.
2. Usar contingencia pre-aprobada **2026-09-22** (Acta 02).
3. Documentar causa (freeze tarde, reinicio por cambio de `config_hash`, gaps B15/B26/B27, serie incompleta).
4. Solo reabrir conversación live con: tear sheet paper OK + firma dual CEO + Desk Lead + checklist `Docs/gates/LIVE_GATE_TEMPLATE.md`.

---

## 6. Prohibido (durante freeze y hasta gate)

- `FORCE_REAL_MODE=true` (o cualquier anulación de paper)
- `PAPER_TRADING=false` con ejecución real / `TRADING_ENABLED=true` hacia exchange
- API keys / secrets de producción en `.env` o imágenes
- Órdenes reales en Binance (mainnet o testnet “por costumbre”)
- Sugerir go-live automático tras un backtest o smoke
- Editar config L0 a mitad de ventana

**Paper-only. Este runbook no autoriza live.**

---

## 7. Veredicto desk (plantilla día 0)

Tras §§1–3:

- **S-TICK_DAY0_READY** — compose paper-safe, freeze + `config_hash` registrado, `effective_mode=paper`, observabilidad up, sin secrets reales.
- o **NO-GO** con owner (ej. hash no escrito, trading-mode ≠ paper, keys prod presentes).
