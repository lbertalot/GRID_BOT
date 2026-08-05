# Inventario vs protocolo Passive Income + plan faseado (GridBot)

**Versión:** 1.15
**Skills de referencia:** `@writing-plans`, `@closed-loop-delivery`, `@tdd-orchestrator`, `@test-driven-development`, `@verification-before-completion`.
**Documentos normativos:** `Docs/PROTOCOL_PASSIVE_INCOME_BOT_V1_ARCHITECTURE.md`, `Docs/GRIDBOT_PASSIVE_INCOME_PRODUCTION_MASTER.md`.
**Plan faseado (orquestación):** `docs/PASSIVE_INCOME_EVOLUTION_PHASED_PLAN.md`.

---

## 1. Inventario — ya existe en GridBot

| Área | Estado | Ubicación / notas |
|------|--------|-------------------|
| API async FastAPI | Sí | `app/main.py`, `app/api/` |
| PostgreSQL + SQLAlchemy + Alembic | Sí | `app/models/`, `alembic/versions/` |
| Redis + Celery + Beat | Sí | `app/core/celery_app.py`, workers |
| Binance + validación filtros | Sí | `BinanceService`, validadores |
| Kelly fraccional + RiskManager | Sí | `app/core/risk_manager.py`, `app/api/risk_routes.py` |
| Circuit breakers + IntegrityGuard | Sí | `app/core/circuit_breakers.py`, `integrity_guard.py` |
| Comisiones (Decimal, puro) | Parcial | `app/services/commission.py` — spread/slippage unificado vive en `transaction_cost_model.py` |
| Comisiones (float, clase) | Parcial | `app/services/commission_manager.py` — conviene converger al modelo central |
| Router HTTP comisiones v1 | Sí | `app/api/commission_routes.py` montado en `app/main.py` (`/api/v1/commissions/*`, incl. audit after-cost) |
| Backtest + costos | Parcial → mejorado | `backtesting_service.py` — `spread_bps`, estrés opcional `cost_stress_two_sigma` (+2σ proxies OHLCV §5.2), `metrics_json` con `transaction_cost_audit`; `tests/test_backtest_cost_integration_p1.py`, `tests/test_execution_cost_two_sigma_stress_p1.py` |
| Reconciliación + métricas | Parcial → mejorado | `TradeAuditor`: auto-reconcile implementado (`_create_missing_internal_trade`, `_update_trade_quantity`, `_update_trade_price`); tests `tests/test_trade_auditor_reconcile_p1.py`; alineación `order_id` string/int en `_compare_trades`; lectura `entry_price` en trades internos |
| ML híbrido River/TF | Sí | `HybridMLEngine`, deps ML Docker |
| DoD Docker local (checklist + defaults compose) | **Cerrado** | `Docs/DOCKER_LOCAL_DOD_CHECKLIST.md`; `tests/test_docker_local_dod_contract_p1.py`; `docker-compose.local.yml` `TRADING_ENABLED=false` por defecto |
| Prometheus / Grafana Docker | Sí | `docker-compose.yml`, `docker-compose.local.yml` |
| Paper / simulación | Sí | flags `PAPER_TRADING`, `BINANCE_TESTNET` |
| OpenTelemetry deps | Sí | `requirements.txt` |
| Research TQS + Monte Carlo + backtest stress + persist backtest + gate ML | Parcial (Fase C) | MC paths/shocks; +2σ backtest; tablas `backtest_runs`/`backtest_metrics`, `persist_run_to_db`; **`monte_carlo_runs`** + `ML_PROMOTION_GATE_PERSIST_MC` (opt-in); FK opcional `backtest_run_id`; retención `KEEP_LAST` + **TTL `MAX_AGE_DAYS`**; **AfterCostBacktestSnapshot** en `promotion_gate.py` + `backtest_gate_loader.py`; **veto NLP opcional** (`ML_PROMOTION_GATE_NLP_*`, Redis); `env.example`/`AGENTS.md`; tests P1 |
| Ops watch | Sí | `scripts/ops_watch/`, `docs/OPS_WATCH_ANTIGRAVITY.md` |

---

## 2. Brechas vs protocolo / maestro

| ID | Brecha | Prioridad | Evidencia |
|----|--------|-----------|-----------|
| G1 | **Modelo único after-cost** (comisión + spread + slippage) serializable para backtest/paper/reportes | **Cerrado (núcleo)** | `transaction_cost_model`, backtest, endpoints audit; residual: converger `commission_manager` (P1) |
| G2 | **TQS** (técnico + cuanti + NLP) | **Parcial** | T+Q: `app/research/tqs_minimal.py`; veto NLP gate: Redis `gridbot:tqs_sentiment:*` + `ML_PROMOTION_GATE_NLP_*` (`promotion_gate_sentiment.py`); persistencia `sentiment_scores` / tablas G3 pendientes |
| G3 | **Tablas protocolo** `sentiment_scores`, `trading_signals` extendidas, ticks hypertable | P1 | Migraciones Alembic nuevas |
| G4 | **Monte Carlo / stress** | **Parcial** | IID + block bootstrap + shocks; gate **TQS + MC + backtest after-cost**; **registro MC** en PG (`monte_carlo_runs`, opt-in); +2σ backtest; persist backtest; **trazabilidad:** FK `backtest_run_id`, retención `KEEP_LAST` + **TTL días** |
| G5 | **Egress IP estático / runbook** API keys | **Cerrado (Fase A)** | `Docs/EGRESS_API_KEYS_RUNBOOK.md` §2.4.5 + cutover; `tests/test_passive_income_p0_ops_contract_p1.py` |
| G6 | **TradeAuditor** auto-reconcile sin stubs | **Cerrado (Fase B núcleo)** | `app/core/trade_auditor.py`; `tests/test_trade_auditor_reconcile_p1.py` |
| G7 | **BYMA / Rofex** adapters | P3 | `BrokerAdapter` + `USE_BROKER_ADAPTER` (TradeExecutor MARKET); venues locales reales §8.1+ pendientes |
| G8 | P99 250 ms presupuesto por etapa | P1 | Medición + refactors puntuales (TF fuera de hot path) |
| **DoD-Docker** | Checklist prod local + defaults seguros | **Cerrado** | `Docs/DOCKER_LOCAL_DOD_CHECKLIST.md` + tests contrato |

---

## 3. Backlog priorizado

### P0 — Producción local creíble + riesgo de simulación honesta

1. ~~**Transaction cost model (after-cost)**~~ **Hecho (núcleo):** modelo + `BacktestingService` + `POST /api/simulations/transaction-cost-audit` + `POST /api/v1/commissions/transaction-cost-audit`.
2. ~~**Runbook egress IP + DoD Docker**~~ **Hecho:** egress + `Docs/DOCKER_LOCAL_DOD_CHECKLIST.md` + `tests/test_docker_local_dod_contract_p1.py` + `TRADING_ENABLED=false` por defecto en `docker-compose.local.yml`.

### P1 — Datos y reconciliación

3. Migraciones: señales + costos en fills (si no existen columnas).
4. ~~Completar `TradeAuditor` paths~~ **Hecho (2026-05-03):** reconciliación DB + `tests/test_trade_auditor_reconcile_p1.py`.
5. ~~Integrar cost model en `BacktestingService`~~ **Hecho** (2026-05-03): `spread_bps`, `vectorbt_fees_and_slippage_from_backtest_fractions`, audit en `run_backtest` → `metrics_json`.

### P2 — Estrategia y ML

6. Pipeline TQS mínimo (técnico + cuanti): **núcleo** en `app/research/tqs_minimal.py`.
6b. Gate promoción ML (TQS + MC + backtest after-cost + NLP veto opcional en ciclo): **núcleo cerrado** — `app/research/promotion_gate.py` (`AfterCostBacktestSnapshot`), `app/services/backtest_gate_loader.py`, `app/services/promotion_gate_sentiment.py`, `trading_tasks._promotion_gate_allows_ml` (async), `ML_PROMOTION_GATE_*` en `env.example` + viñeta `AGENTS.md`; métricas `reason` ampliadas en `docs/08-metrics-catalog.md`.
7. ~~NLP + Redis cache (veto + escala Kelly acotada).~~ **Veto en gate (parcial):** `ML_PROMOTION_GATE_NLP_*`, `app/services/promotion_gate_sentiment.py`; **escala Kelly acotada (2026-05):** `KELLY_SENTIMENT_SCALE_*`, `kelly_multiplier_from_sentiment_score`, ciclo `trading_tasks` (fase evaluación), métrica `gridbot_kelly_sentiment_scale_total`, tests `tests/test_kelly_sentiment_scale_p1.py`.
8. Monte Carlo: IID + **block bootstrap** + pytest + shocks §5.2 — `monte_carlo_paths.py`, `monte_carlo_shocks.py`.

### P3 — Local argentino

9. ~~`BrokerAdapter` diseño + TradeExecutor + HTTP + grid SELL~~ **Hecho:** `USE_BROKER_ADAPTER`; `trade_executor.py`; `broker_market_execution.place_spot_market_via_adapter`; `app/api/trade.py` MARKET; `OptimizedGridManager` SELL real; métrica `gridbot_spot_market_submit_path_total`; tests API + grid P1.

---

## 4. P0 — Criterios de aceptación y tests acordados

### Historia

Como operador, quiero un **único lugar** que calcule y exporte **fricción total** (comisión + spread modelado + slippage modelado) sobre el **notional** en quote (p. ej. USDT) usando `Decimal`, para backtests y paper auditables.

### Tests (`tests/test_transaction_cost_model_p1.py` + `tests/test_backtest_cost_integration_p1.py`)

1. `test_rejects_non_positive_notional` — `ValueError` si notional ≤ 0.
2. `test_buy_total_friction_increases_with_spread_and_slippage` — BUY: fricción total ≥ comisión sola; sube con bps.
3. `test_sell_symmetric_friction` — SELL: misma magnitud de fricción en notional que BUY para mismos bps (modelo simétrico en quote).
4. `test_commission_maker_vs_taker` — LIMIT/maker vs MARKET/taker coherente con `CommissionRates`.
5. `test_audit_to_dict_json_serializable` — salida apta para `json.dumps`.
6. Integración backtest: mapeo vectorbt sin `spread_bps` = compat; con spread suma a slippage; validación `BacktestConfig`; auditoría referencia coherente.

### Definición de Done P0 — bloque after-cost (cerrado)

- [x] Tests P1 modelo + integración backtest en verde (`pytest tests/test_transaction_cost_model_p1.py tests/test_backtest_cost_integration_p1.py tests/test_transaction_cost_audit_endpoint.py -q`).
- [x] Endpoints audit bajo auth; métrica `gridbot_transaction_cost_audit_requests_total`.
- [x] **P0 ops:** `tests/test_passive_income_p0_ops_contract_p1.py` en verde (`Docs/PASSIVE_INCOME_EVOLUTION_PHASED_PLAN.md` §3).

### Definición de Done P0 — doc / ops + DoD Docker (cerrado)

- [x] Runbook egress alineado a protocolo §2.4.5 + tests contrato.
- [x] `Docs/DOCKER_LOCAL_DOD_CHECKLIST.md` + `tests/test_docker_local_dod_contract_p1.py`; defaults seguros en `docker-compose.local.yml`.
- [x] Referencia desde `AGENTS.md` al checklist DoD y variables de arranque.

---

## 5. Producción local Docker (checklist verificación)

Ver **fuente normativa:** `Docs/DOCKER_LOCAL_DOD_CHECKLIST.md`. Resumen:

- [x] `docker compose -f docker-compose.local.yml` — api, worker, beat, db, redis, observabilidad según archivo compose.
- [x] `curl -sf http://localhost:8000/health`.
- [x] `PAPER_TRADING` / `TRADING_ENABLED` / `EMERGENCY_STOP` documentados para arranque seguro.
- [ ] `make ops-watch-once` opcional post-cambio (`docs/OPS_WATCH_ANTIGRAVITY.md`).

---

## 6. Próximo paso tras Fase C (registro MC + gate)

- **Fase C (residual):** ~~veto NLP vía Redis en gate~~ **Hecho (2026-05):** `ML_PROMOTION_GATE_NLP_*`; ~~escala Kelly acotada por sentimiento~~ **Hecho (2026-05):** `KELLY_SENTIMENT_SCALE_ENABLED`, mismo Redis `gridbot:tqs_sentiment:*`; enriquecimientos TQS (sin G3 hasta issue).
- ~~Política de retención `monte_carlo_runs`~~ **Hecho:** `ML_PROMOTION_GATE_MC_RETENTION_KEEP_LAST`, `ML_PROMOTION_GATE_MC_RETENTION_MAX_AGE_DAYS` (TTL), FK `backtest_run_id` hacia `backtest_runs`.
- **Datos:** G3 solo con issue aprobado (migraciones Alembic).
- **Fase D (Fase 0):** contrato `BrokerAdapter` + Binance spot + stubs BYMA/Rofex.
- **Cableado adapter MARKET:** TradeExecutor; `POST /order`; grid **SELL** real; métricas `gridbot_trade_executor_order_path_total`, `gridbot_spot_market_submit_path_total`.

---

*Actualizar al cerrar cada fase (`@verification-before-completion`).*
