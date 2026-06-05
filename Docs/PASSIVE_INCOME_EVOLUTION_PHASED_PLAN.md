# Plan de evolución GridBot → Passive Income v1.x (orquestado)

**Versión:** 1.15
**Norma:** `Docs/PROTOCOL_PASSIVE_INCOME_BOT_V1_ARCHITECTURE.md`, `Docs/GRIDBOT_PASSIVE_INCOME_PRODUCTION_MASTER.md`.
**Reglas:** `AGENTS.md`, `.cursorrules`, `docs/TDD_WORKFLOW.md`, `docs/CICD_RUNBOOK.md`, `TESTING_RULES.md`.

---

## 0. Declaración de skills por fase (Antigravity / Awesome)

| Fase | Objetivo | Skills explícitos |
|------|-----------|-------------------|
| Inventario y backlog | Tareas acotadas, criterios de aceptación, sin scope creep | `@writing-plans`, `@concise-planning`, `@closed-loop-delivery` |
| Diseño / arquitectura | Multi-venue, riesgo, ADR-capable | `@software-architecture`, `@backend-architect` (diseño; código en servicios) |
| TDD e implementación | RED-GREEN-REFACTOR; P1 financiero primero | `@tdd-orchestrator`, `@test-driven-development` |
| Tests rotos / bugs | Causa raíz antes del parche | `@systematic-debugging`, `@phase-gated-debugging`, `@bug-hunter` |
| Calidad y regresión | Smells, gates | `@find-bugs`, `@lint-and-validate` |
| Observabilidad / Docker | Salud, compose, métricas | `@antigravity-workflows`, `@observability-engineer`, `@docker-expert`, `@devops-deploy` |
| Cierre de fase | Evidencia obligatoria | `@verification-before-completion` |
| Documentación | Runbooks, endpoints, env | `@documentation-generation-doc-generate`; toques `AGENTS.md` vía `@agents-md` solo si aporta comandos/vars nuevas |
| CI (solo si se toca) | Jobs y seguridad | `@cicd-automation-workflow-automate`, `@github-actions-templates` |

**Post-cambio relevante:** flujo `docs/OPS_WATCH_ANTIGRAVITY.md` (`make ops-watch-once`) cuando cambien servicios observables.

---

## 1. Inventario actualizado (protocolo ↔ repo)

### 1.1 Cerrado o cubierto en núcleo (2026-Q1)

| Requisito protocolo / maestro | Estado | Evidencia en repo |
|-------------------------------|--------|-------------------|
| §3.4 After-cost auditable (comisión + spread + slippage) | **Cerrado v1** | `app/services/transaction_cost_model.py`; backtest `BacktestConfig.spread_bps` + `metrics_json`; `POST /api/simulations/transaction-cost-audit` y `POST /api/v1/commissions/transaction-cost-audit` |
| §3.1 Kelly fraccional / riesgo | Existente | `RiskManager`, `risk_routes` |
| §3.3 Breakers / kill-switch | Existente | `CircuitBreakers`, `EMERGENCY_STOP`, `TRADING_ENABLED`, IntegrityGuard |
| TQS + Monte Carlo + estrés costos + persistencia backtest + gate ML + **registro MC** | **Parcial (Fase C)** | MC + backtest stress; `backtest_runs`/`backtest_metrics`; **`monte_carlo_runs`** + `ML_PROMOTION_GATE_PERSIST_MC`; gate `promotion_gate` + `backtest_gate_loader`; vars `env.example`/`AGENTS.md` |
| §2.1 Stack FastAPI / PG / Redis / Celery / Prometheus | Existente | Compose, `app/core/metrics.py` |
| Paper / validación sin real | Existente | `PAPER_TRADING`, dry-run simulaciones |

### 1.2 Brechas activas (prioridad)

| ID | Brecha | Prioridad | Notas |
|----|--------|-----------|--------|
| **G5** | Egress IP + runbook operativo al nivel §2.4.5 (monitoreo, cutover dual-key, alerta cambio egress) | **Cerrado (Fase A)** | Runbook + `tests/test_passive_income_p0_ops_contract_p1.py` |
| **DoD-Docker** | “Prod local 100 % dockerizada” con checklist verificable y defaults seguros documentados | **Cerrado (Fase A′)** | `Docs/DOCKER_LOCAL_DOD_CHECKLIST.md`; `TRADING_ENABLED=false` en `docker-compose.local.yml`; `tests/test_docker_local_dod_contract_p1.py` |
| G1-residual | Convergencia `commission_manager` → modelo central after-cost | P1 | Deuda técnica; no bloquea promoción paper si API audit existe |
| G6 | `TradeAuditor` sin stubs | **Cerrado (Fase B núcleo)** | `trade_auditor.py` + `tests/test_trade_auditor_reconcile_p1.py` |
| G2 | TQS completo (NLP veto, persistencia señales) | P2 | Núcleo T+Q en `app/research/tqs_minimal.py`; **veto NLP gate** Redis + env (`promotion_gate_sentiment.py`); persistencia `sentiment_scores` pendiente |
| G4 | Monte Carlo protocolo completo (shocks, registro corridas) | P2 | IID + block bootstrap + shocks §5.2; +2σ backtest; persist backtest; **registro MC** en PG (opt-in); **retención** (`KEEP_LAST`, TTL días), **FK** `backtest_run_id`; enriquecimientos NLP pendientes |
| G3 | Tablas `sentiment_*`, señales extendidas, hypertable ticks | P1 | Alembic |
| G7 / G8 | BYMA, P99 | P2–P3 | Roadmap posterior |

---

## 2. Backlog faseado (sin scope creep)

### Fase A — P0 Ops y arranque seguro (**cerrada**)

**Objetivo:** Cumplir criterios de aceptación protocolo §2.4.5 a nivel documentado + contrato comprobable; reforzar DoD Docker local y variables de riesgo en docs.

**Entregables (hechos):**

1. `Docs/EGRESS_API_KEYS_RUNBOOK.md` ampliado (cutover, egress, monitoreo mínimo).
2. Checklist arranque seguro: `AGENTS.md` + **`Docs/DOCKER_LOCAL_DOD_CHECKLIST.md`**; defaults `docker-compose.local.yml` (`TRADING_ENABLED=false`).
3. Tests contrato: `tests/test_passive_income_p0_ops_contract_p1.py`, `tests/test_docker_local_dod_contract_p1.py`.

**No incluido en Fase A:** implementación de job Prometheus “egress check”, multi-venue CCXT, TQS.

### Fase B — P1 Datos y reconciliación

**Objetivo:** G6 cerrado o alcance explícitamente acotado con tests; migraciones G3 solo si hay issue aprobado.

**Skills:** `@tdd-orchestrator`, `@test-driven-development`, `@verification-before-completion`.

### Fase C — P2 Señal y validación estadística (**en curso — núcleo mínimo entregado**)

**Objetivo:** Pipeline TQS mínimo (T+Q sin NLP); Monte Carlo / stress (`G4`) con semilla en pytest.

**Entregables (hechos v0):**

1. `app/research/tqs_minimal.py` — ROC (técnico) + cruce EMA (cuanti) → `TqsSnapshot` (Pydantic).
2. `app/research/monte_carlo_paths.py` — bootstrap IID o **moving block** (`bootstrap_mode`, `block_size`); shocks opcionales.
3. `app/research/monte_carlo_shocks.py` — multiplicadores `(1+r)` día único y racha 3 días; RNG por trayectoria sin alterar el muestreo bootstrap.
4. Tests: `tests/test_tqs_minimal_p1.py`, `tests/test_monte_carlo_paths_p1.py`, `tests/test_monte_carlo_shocks_p1.py`, `tests/test_monte_carlo_block_bootstrap_p1.py`.
5. Gate promoción ML (opcional en ciclo): `app/research/promotion_gate.py` (`AfterCostBacktestSnapshot` + reglas MC/backtest), `app/services/backtest_gate_loader.py`, `klines_utils.py`; `ML_PROMOTION_GATE_*` documentadas en `env.example` y `AGENTS.md`; shocks MC, `ML_PROMOTION_GATE_MC_BOOTSTRAP` (`iid`|`block`), `ML_PROMOTION_GATE_MC_BLOCK_SIZE`; tests `test_promotion_gate_p1.py`, `test_trading_tasks_promotion_gate_p1.py` (JSON + **SessionLocal** SQLite persistido), `test_backtest_gate_loader_p1.py`.
6. Estrés ejecución §5.2 en backtest: `transaction_cost_model` (+2σ OHLCV); `BacktestConfig.cost_stress_two_sigma`; test `tests/test_execution_cost_two_sigma_stress_p1.py`.
7. Persistencia corridas backtest (§D): modelos `BacktestRun`/`BacktestMetric`, migración `alembic/versions/20260503_backtest_runs_tables.py`, `persist_completed_backtest_run`, `persist_run_to_db` + API `BacktestRequest.persist_run_to_db`; test `tests/test_backtest_persistence_p1.py`.
8. Persistencia estudios Monte Carlo del gate: modelo `MonteCarloRun`, migración `20260504_monte_carlo_runs_table.py`, `persist_monte_carlo_drawdown_study`, `ML_PROMOTION_GATE_PERSIST_MC`, métrica `gridbot_monte_carlo_run_persist_total`; tests `tests/test_monte_carlo_persistence_p1.py` + fila en `test_trading_tasks_promotion_gate_p1.py`.
9. Veto NLP opcional en gate: `app/services/promotion_gate_sentiment.py`, `ML_PROMOTION_GATE_NLP_*`, razones `nlp_sentiment_below_min` / `nlp_sentiment_unavailable`; tests `tests/test_promotion_gate_sentiment_p1.py`; `_promotion_gate_allows_ml` async.

**Pendiente (no bloquea Fase C v0):** escala Kelly acotada por sentimiento; particionado `monte_carlo_runs` (opcional, operación futura).

**Cerrado (2026-05):** retención — `ML_PROMOTION_GATE_MC_RETENTION_KEEP_LAST`, `ML_PROMOTION_GATE_MC_RETENTION_MAX_AGE_DAYS` (TTL); enlace MC ↔ `backtest_run_id` + `ML_PROMOTION_GATE_MC_ATTACH_BACKTEST_RUN_ID`.

### Fase D — P3 Venues locales (**Fase 0 contrato — entregada v0**)

**Objetivo:** `BrokerAdapter` diseño + primera implementación Binance spot; BYMA/Rofex stub hasta proveedor.

**Entregables (2026-05):**

1. Paquete `app/services/broker_adapter/`: tipos Pydantic (`Decimal`), `BrokerAdapter` (`typing.Protocol`), `BinanceSpotBrokerAdapter` (delega en `AsyncBinanceWrapper`), `UnimplementedVenueBrokerAdapter`, `create_broker_adapter` / `BROKER_PRIMARY_VENUE`, `USE_BROKER_ADAPTER` → **TradeExecutor** órdenes MARKET.
2. Tests `tests/test_broker_adapter_p1.py`, `tests/test_trade_executor_broker_adapter_p1.py`.
3. **Cableado adicional (2026-05):** `app/services/broker_market_execution.place_spot_market_via_adapter`; `POST /order` y `/api/trade/order` MARKET vía adapter + fallback `-1021`; `OptimizedGridManager._place_order` **SELL** real vía adapter (reutiliza `async_binance`); BUY real sigue `quoteOrderQty`; métrica `gridbot_spot_market_submit_path_total`; tests `tests/test_trade_api_broker_adapter_p1.py`, `tests/test_optimized_grid_manager_broker_adapter_p1.py`.

**Pendiente:** extender `BrokerAdapter` (LIMIT, otros venues BYMA/Rofex reales); BUY grid con cantidad base por adapter (opcional; hoy `quoteOrderQty`).

## 3. Acuerdo RED (primer ítem P0 = Fase A)

**Regla de orquestación:** no implementar lógica de producto nueva hasta que existan los tests RED siguientes (archivo y nombres fijos para el siguiente PR de TDD).

**Archivo propuesto:** `tests/test_passive_income_p0_ops_contract_p1.py`

| # | Nombre del test (obligatorio) | Comportamiento esperado (RED → luego GREEN) |
|---|-------------------------------|---------------------------------------------|
| 1 | `test_egress_runbook_exists` | `Docs/EGRESS_API_KEYS_RUNBOOK.md` existe y tamaño > 500 caracteres (evita runbook vacío). |
| 2 | `test_egress_runbook_covers_protocol_section_keywords` | El runbook contiene (case-insensitive) las subcadenas: `whitelist`, `NAT` o `egress`, `rotación` o `rotacion` o `rotaci`, `retiro` o `withdraw`, `PAPER_TRADING`, `TRADING_ENABLED`. |
| 3 | `test_evolution_phased_plan_exists` | `Docs/PASSIVE_INCOME_EVOLUTION_PHASED_PLAN.md` existe (auto-referencia del contrato de evolución). |
| 4 | `test_agents_md_mentions_critical_trading_env_vars` | `AGENTS.md` menciona `PAPER_TRADING`, `TRADING_ENABLED`, `EMERGENCY_STOP` (o equivalente documentado). |
| 5 | `test_compose_local_or_main_documents_db_redis_api` | Al menos uno de: `docker-compose.local.yml` o `docker-compose.yml` contiene servicios `db`/`postgres` y `redis` y referencia a `api` o documentado en mismo archivo que la API se levanta en perfil local (string search `redis`, `api`/`uvicorn`/`fastapi` según convención del repo). |

**Notas:**

- Son tests de **contrato de documentación/compose**; no sustituyen tests QAA de trading.
- Tras RED: implementar solo ampliaciones de markdown/yaml necesarias para verde; no añadir endpoints salvo nuevo issue P0.

**Comando verificación fase:** `python3.11 -m pytest tests/test_passive_income_p0_ops_contract_p1.py -q`

---

## 4. Definition of Done (global del programa — recordatorio)

1. **TDD:** nuevo comportamiento con tests; `pytest -q` verde; `tests/test_qaa_*.py` verde.
2. **Docs:** `Docs/` actualizado; métricas nuevas en `Docs/08-metrics-catalog.md` si aplica.
3. **Docker local:** comandos explícitos; health `/health`; migraciones aplicables; trading real **desactivado por defecto** en guías.
4. **Secretos:** nunca en repo; checklist keys sin withdraw donde aplique.
5. **Observabilidad:** prefijos métricas del proyecto; Grafana/import según repo.

---

## 5. Riesgos residuales y capital real

- **Capital real** queda fuera hasta: egress verificado, paper estable, reconciliación sin stubs críticos, gates cuantitativos definidos en maestro § promoción ML.
- **Riesgo:** dependencia de Binance whitelist sin NAT estático → mitigación solo vía G5.

---

**Próximo hito lógico:** escala Kelly acotada por sentimiento (residual Fase C); **G3** migraciones Alembic (`sentiment_scores`, señales, costos en fills) **solo con issue aprobado**; convergencia `commission_manager` → modelo after-cost (G1-residual); límites/CCXT en `BrokerAdapter` (P3).
