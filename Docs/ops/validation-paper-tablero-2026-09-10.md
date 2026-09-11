# Tablero único — validación paper → piloto

**Generado:** 2026-09-10T13:46Z  
**Owner:** Desk Lead  
**Modo:** paper-only · `PAPER_TRADING=true` · `FORCE_REAL_MODE` vacío · **PROMOTE_LIVE: NO**  
**No wipe** Redis / ledger / rachas / `paper_telemetry`.

Fuentes: [day28-action-plan-2026-09-10.md](day28-action-plan-2026-09-10.md) · [trial-si-5x15-2026-09-09.md](trial-si-5x15-2026-09-09.md) · [TEAR_SHEET_PAPER_30D.md](../TEAR_SHEET_PAPER_30D.md) · [tear-sheet-paper-30d-fase0-2026-09-10.md](tear-sheet-paper-30d-fase0-2026-09-10.md)

---

## Invariantes

- No live, no apalancamiento, no `FORCE_REAL_MODE`, no aumento de capital.
- Ventana 30d canónica: 2026-08-15 → 2026-09-14 UTC. Desplegado **USD 200**.
- Métricas = equity MtM neta de fees/slippage. Prohibido KPI `trades.profit_loss`.
- Un agente no edita archivos de otro sin nota aquí.
- Árbol sucio de breakers/Grafana/Prom: preservar; no `checkout`/`reset`.

## Resumen diario (2026-09-10 ~13:46Z)

| Campo | Valor |
|-------|-------|
| Modo | paper · `trading_enabled=false` (post-cierre trial) · `emergency_stop=false` |
| Equity MtM | **999.0232991152** USDT (E_0=1000) |
| PnL neto MtM | **−0.9767** USDT (−0.098% vs E_0 · −0.488% vs desplegado 200) |
| MaxDD desplegado | **0.488%** (≤5% numérico; no compensa PnL &lt; 0) |
| Freno | `system_integrity` **OPEN + REDUCE_ONLY** (NO-GO 5×15; no resetear) |
| Snapshot | ~50 s (Prom `job=gridbot-api`); umbral 20 min OK |
| Tick Celery | `trading_cycle_tick` ~1/min, status ok |
| Alertas Prom firing | 0 al muestreo 13:33Z |
| Acciones | Cerrar ventana 30d el 14-sep como `ITERATE` o `REJECT`. No live. |

Sin claim de edge. Dinero real: NO.

## Observabilidad — Telegram / Grafana (2026-09-10)

| Campo | Valor |
|-------|-------|
| Causa | Telegram decía “varios cierres seguidos en pérdida” para SI NO-GO (0 closes post-t0). Grafana Paper L0 mostraba PnL/portfolio ops como si fueran SoT. |
| Decisión | Copy SI estructurado (`breaker_type`, REDUCE_ONLY, motivo NO-GO). Racha leída del ledger (sin número inventado). Causa desconocida → integridad en revisión. Reaviso 6 h. “Freno levantado” solo en transición abierto→cerrado. Paneles ops rotulados **no SoT**. |
| No se tocó | Redis HASH, SI, ledger, racha 19, sizing, `FORCE_REAL_MODE`, queries Grafana. |
| Evidencia | 94 passed (python3.11, 2026-09-11): suites pedidas + `test_binance_auth_ip_watch` `test_fase0_close_checklist` `test_paper_fill_client_order_id` `test_paper_recon_identity` `test_order_backend_guards` |

## Cierre controlado 14-sep 00:00 UTC (read-only)

Checklist automático (números del tear 2026-09-10; refrescar en el close sin wipe):

| Ítem | Valor | Gate |
|------|-------|------|
| Cierres 00:00 UTC | daily_close_at 24 (hace falta ≥30) | A2 |
| Gaps | `gaps>2h count=13→17` · max **126.07 h** = stack offline **2026-09-04T11:07Z→2026-09-09T17:11Z** ([RCA](rca-gap126h-hash-drift-2026-09-11.md)) | A2 **FAIL** |
| Equity MtM | 999.0233 vs E₀ 1000 | SoT ledger |
| PnL neto | −0.9767 USDT | Capa B **rojo** |
| MaxDD desplegado | 0.488% | ≤5% numérico |
| Ciclos | 19 (≪ 120) | **rojo** |
| Hashes | serie `ac1cb596…` (sticky pre-qty-fix) ≠ sidecar `ff6a35fc…`; fills 38/38 qty `0.0082` ([RCA](rca-gap126h-hash-drift-2026-09-11.md)) | A1 deuda / P0 instrumentación |
| Breakers | SI OPEN NO-GO 5×15; no resetear | paper |
| Modo | `PAPER_TRADING=true` · `FORCE_REAL_MODE` vacío · no live | R-1 |

Veredicto preliminar calculado (`fase0_close_verdict`): **ITERATE** (A2 rojo **o** PnL neto &lt; 0 **o** ciclos insuficientes).  
**No** `PROMOTE_PAPER`. **PROMOTE_LIVE: NO.**

**Firma humana pendiente** — Cursor no firma DL-4. Desk Lead el 14-sep: `ITERATE` o `REJECT`.

Hotfix 2026-09-11: un fingerprint SI (no `OPEN · CLOSED`); −2015 = `binance_auth_ip_blocked` 6 h; runbook IP humano.

Fase 2: [fase2-gate-2026-09-22.md](fase2-gate-2026-09-22.md) **bloqueada**.

## Goal live-ready — PASO 0 (2026-09-11) — RESUELTO

Prueba 5×15 intento 3: **CERRADO — NO-GO** ([trial §8](trial-si-5x15-2026-09-09.md)). Runtime N10; SI OPEN = residuo NO-GO (no resetear).  
**PASO 0 = (b):** acta §8 = cierre formal Desk Lead.  
Dossier cerrado: [dossier-live-ready-or-nogo-2026-09-11.md](dossier-live-ready-or-nogo-2026-09-11.md) → **NO-GO live**. **PROMOTE_LIVE: NO.**  
Fase 0 paper: veredicto preliminar **ITERATE** (firma DL-4 humana el 14-sep). Fase 2 **bloqueada**.

---

## Fases

| Fase | Fechas | Estado | Veredicto |
|------|--------|--------|-----------|
| 0 Cerrar ventana | hasta 2026-09-14 | **EN CURSO** | preliminar **ITERATE** (A2 rojo, 19 ciclos, PnL &lt; 0). Firma DL-4 el 14-sep |
| 1 Auditoría | 2026-09-15 → 21 | Lista de trabajo | [fase1-action-plan-2026-09-15.md](fase1-action-plan-2026-09-15.md) |
| 2 Paper OOS | 2026-09-22 → 10-21 | Bloqueada | exige config congelada + Capa A/B verdes |
| 3 Resiliencia | 2026-10-22 → 11-18 | Bloqueada | — |
| 4 Comité piloto USD 600 | desde 2026-11-19 | Bloqueada | dos ventanas independientes + seguridad |

`PROMOTE_PAPER` imposible hoy. `PROMOTE_LIVE` **no existe** en este tablero.

---

## Acta gates

| Gate | Fecha | Decisión | Firma |
|------|-------|----------|-------|
| SI 5×15 intento 3 | 2026-09-10 | **NO-GO prueba** (0 closes post-t0; idle 12 h) | Desk Lead — contrato trial §2 ya firmado 2026-09-09 |
| Tear 30d | 2026-09-14 | pendiente `REJECT` \| `ITERATE` | no firmar `PROMOTE_PAPER` |
| Piloto real | — | no aplica | capital 600 / pérdida máx. 30 solo con firma humana posterior |

---

## Backlog

P0 = Fase 0 (esta semana). P1 = Fase 1. P2+ = ventanas siguientes.

### Desk Lead

| ID | Pri | Estado | Tarea | Tests / evidencia | Gate |
|----|-----|--------|-------|-------------------|------|
| DL-1 | P0 | **DONE** | Este tablero | este archivo | versionado; sin live |
| DL-2 | P0 | **DONE** | Contar `closed_at > t0` y aplicar §2 | ledger: hist 19 / post_t0 **0**; SI reason NO-GO; recreate `--no-deps` | no wipe racha 19; no 2º override |
| DL-3 | P0 | OPEN | Cierres 00:00 UTC ±30m días 28–30 | [RUNBOOK_DAILY_CLOSE_PAPER_L0.md](RUNBOOK_DAILY_CLOSE_PAPER_L0.md) | `daily_close_at` |
| DL-4 | P0 | OPEN | Firmar tear 14-sep | [tear-sheet-paper-30d-fase0-2026-09-10.md](tear-sheet-paper-30d-fase0-2026-09-10.md) | `REJECT` o `ITERATE` |
| DL-5 | P1 | OPEN | Una variante congelada para Fase 2 | N10 10×20 vs no reutilizar 5×15 (no validó) | un hash antes del 22-sep |
| DL-6 | P4 | BLOCKED | Piloto USD 600 | dos ventanas verdes | firma humana; 0× leverage |

### Quant

| ID | Pri | Estado | Tarea | Tests / API | Gate |
|----|-----|--------|-------|-------------|------|
| Q-1 | P0 | **DONE** | Serie 30d sin mezclar 5×15 | 0 closes post-t0; 19 pre-watermark | no inventar |
| Q-2 | P0 | **DONE** | Plantilla spec §5 | tear Fase 0 | números o N/A |
| Q-3 | P1 | **DONE 2026-09-10** | Auto Capa A = spec | `tests/test_desk_tear_capa_a_spec.py` | A1 único hash; A3 recon; A5 fees; A8 paper |
| Q-4 | P1 | OPEN | Hipótesis tendencia spot offline | research only | una variante; no in-sample |
| Q-5 | P2 | OPEN | Tear Fase 2 | spec §2 | todas verdes o no avanza |

### Risk & Security

| ID | Pri | Estado | Tarea | Tests | Gate |
|----|-----|--------|-------|-------|------|
| R-1 | P0 | **DONE** | `PAPER_TRADING=true` api/worker/beat | `/health` paper; compose `PAPER_TRADING: "true"` | cero órdenes reales |
| R-2 | P0 | **DONE** | SEC ≠ ciclo paper ON | `test_collect_sec_on_when_paper_cycle_enabled` | `FORCE_REAL_MODE` sí marca OFF |
| R-3 | P0 | **DONE** | Scan logs keys | `test_log_secret_redaction.py`; host logs 0 hits | cero substrings |
| R-4 | P1 | OPEN | Fail-closed Redis/PG/ticker | `test_breaker_store_defense_cba.py` | stop bloquea órdenes |
| R-5 | P1 | OPEN | Runbook stop sin wipe | [breakers-process-scope.md](breakers-process-scope.md) | `--no-deps` only |
| R-6 | P1 | OPEN | Key Binance sin retiro | checklist humano | no pegar la key |

### Trading Systems

| ID | Pri | Estado | Tarea | Tests | Gate |
|----|-----|--------|-------|-------|------|
| T-1 | P0 | **DONE** | Closes post-watermark | 0 filas; racha 19 intacta | tabla post-t0 vacía |
| T-2 | P0 | **DONE** | No retocar sizing; revertir overlay | compose N10; sidecar `ff6a35fc…` | N10 en disco intacta |
| T-3 | P1 | OPEN | Fees/slippage/filtros/`client_order_id` | ledger: 38/38 fees; **0** `client_order_id` | 100% commission; 0 dups |
| T-4 | P1 | OPEN | SoT ledger vs inventario vs equity | cash 999.02 · inv 0 · E 999.02 | ≤0,1% |
| T-5 | P1 | OPEN | Congelar un hash Fase 2 | serie hoy `ac1cb596…` ≠ sidecar N10 | A1 punta a punta |

### Observability & SRE

| ID | Pri | Estado | Tarea | Tests / rules | Gate |
|----|-----|--------|-------|---------------|------|
| O-1 | P0 | **DONE** | Snapshot &lt;20 min; tick 1/min | Prom age 50 s post-recreate; tick ok | sin crítica abierta |
| O-2 | P0 | **DONE** | Resumen 1 página | sección arriba | sin claim edge |
| O-3 | P1 | OPEN | Verificar entrega de alertas existentes | `HighDailyDrawdown`, `CircuitBreakerActivated`, `PaperSnapshotStale20m` | disparan y llegan |
| O-4 | P3 | OPEN | Chaos sin `-v` ni DEL HASH | smoke 2026-08-30 | sin pérdida/duplicación |

### QA

| ID | Pri | Estado | Tarea | Suite | Gate |
|----|-----|--------|-------|-------|------|
| QA-1 | P0 | **DONE** | Registro de comandos | § Evidencia QA abajo | reproducible |
| QA-2 | P0 | **DONE** | Contrato Docker + health/breakers | `test_docker_local_dod_contract_p1.py` | paper-safe |
| QA-3 | P1 | OPEN | TDD antes de bugs de riesgo | Decimal | no bajar cobertura P1 |
| QA-4 | P1 | **DONE** | Tests Capa A spec | `tests/test_desk_tear_capa_a_spec.py` | A1–A8 alineados |
| QA-5 | P1 | OPEN | Regresión QAA + breakers | `pytest tests/test_qaa_*.py tests/test_breaker_*.py` | verde |

---

## Preservación del árbol (dueños)

| Área | Archivos — no pisar sin coordinación |
|------|--------------------------------------|
| Risk | `app/core/circuit_breakers.py`, `breaker_state_store.py`, `breaker_override.py`, `auto_circuit_breaker.py`, `tests/test_breaker_*` |
| SRE | Grafana dashboards, `paper_obs_p0_rules.yml` (compose: Desk Lead cerró overlay 5×15) |
| MM / TS | `grid_config_paper_l0*.json`, overlay trial (archivo intacto, ya no runtime) |
| Docs auto | `day*-action-plan-*`, `tear-capa-a-YYYY-MM-DD.md` append-only |

---

## Evidencia QA (comandos 2026-09-10)

```text
# Ledger trial
python3: hist 19  post_t0 0  max_closed_at=2026-08-26T15:45:37.370240+00:00

# Health post-cierre overlay
GET /health → paper_trading=true force_real_mode=false trading_enabled=false
              emergency_stop=false effective_mode=paper live_gate_signed=false

# Breakers (Redis TYPE hash; no DEL)
GET /breakers/summary → active_breakers=["system_integrity"] REDUCE_ONLY NO-GO prueba

# Worker
PAPER_TRADING=true TRADING_ENABLED=false GRID_CONFIG_FILE=grid_config_paper_l0.json
GRID_CONFIG_HASH=ff6a35fc… PAPER_TRIAL_STARTED_AT=UNSET PAPER_EARLY_STREAK_WARN=3

# Recreate
docker compose -f docker-compose.local.yml up -d --no-deps --force-recreate api worker beat
# redis/db intactos (Up 20 hours)

# Tests (python3.11)
pytest tests/test_desk_hourly_status.py::test_collect_sec_on_when_paper_cycle_enabled \
       tests/test_desk_hourly_status.py::test_collect_off_track_force_real \
       tests/test_desk_tear_capa_a_spec.py \
       tests/unit/test_desk_tear_and_area_actions.py \
       tests/test_docker_local_dod_contract_p1.py \
       tests/test_paper_mode_flag.py \
       tests/test_log_secret_redaction.py \
       tests/test_paper_trial_si_5x15_overlay.py -q
# resultado: 50 passed (python3.11, 2026-09-10T13:47Z)

# Secret scan host logs/*.log : full_key_files=0 prefix8=0
```

**PROMOTE_LIVE: NO.**
