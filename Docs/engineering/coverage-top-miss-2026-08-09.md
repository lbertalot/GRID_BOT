# Coverage top-miss — 2026-08-09 (S-COV-85 Wave 0.1)

**Repo:** `GRID_BOT/` · branch baseline `main` → worktree `test/s-cov-85-wave0-1.1`  
**Generado:** 2026-08-09 01:15 UTC  
**Runner:** `python3.11 -m pytest tests/ -q --cov=app --cov-report=xml:coverage.xml`  
**Env paper-safe:** `PAPER_TRADING=true FORCE_REAL_MODE=false TRADING_ENABLED=false USE_REAL_BINANCE=0 CI=true EMERGENCY_STOP=true`  
**Resultado suite:** 1093 passed, 152 skipped · **cobertura app:** **43.00%** (8818/20505 líneas)  
**Artifact:** `coverage.xml` local (no commit; regenerar en CI).

## Nota metodológica

- Suite completa en host py3.11 (~90s). CI=true auto-skippea E2E HTTP y archivos con drift documentado en `tests/conftest.py`.
- Codecov UI main reportaba ~63.38%; local 43% es **más bajo** porque la suite local omite más paths/import side-effects que el job CI completo — usar esta tabla como cola de leverage, no como score Codecov.
- Heurística §7 del brief se reemplaza por miss count real abajo.

## Top 50 archivos por líneas miss

| Rank | Miss | Cover % | Hit/Total | Path |
|-----:|-----:|--------:|----------:|------|
| 1 | 584 | 21.3% | 158/742 | `services/trading_tasks.py` |
| 2 | 548 | 25.5% | 188/736 | `core/optimized_grid_manager.py` |
| 3 | 370 | 0.0% | 0/370 | `services/hybrid_ml_engine.py` |
| 4 | 338 | 0.0% | 0/338 | `services/config_manager.py` |
| 5 | 336 | 0.0% | 0/336 | `scheduler/optimized_scheduler.py` |
| 6 | 320 | 25.8% | 111/431 | `services/binance_client_singleton.py` |
| 7 | 310 | 10.1% | 35/345 | `services/metrics_service.py` |
| 8 | 296 | 12.7% | 43/339 | `core/integrity_monitor.py` |
| 9 | 284 | 33.6% | 144/428 | `main.py` |
| 10 | 276 | 13.8% | 44/320 | `core/balance_validator.py` |
| 11 | 271 | 12.3% | 38/309 | `services/auto_rebalancer_v2.py` |
| 12 | 248 | 12.4% | 35/283 | `services/binance_user_stream.py` |
| 13 | 244 | 0.0% | 0/244 | `exchanges/binance_client.py` |
| 14 | 231 | 23.8% | 72/303 | `services/binance_data_sync.py` |
| 15 | 227 | 0.0% | 0/227 | `services/performance_analyzer.py` |
| 16 | 225 | 38.2% | 139/364 | `services/binance_service.py` |
| 17 | 216 | 22.9% | 64/280 | `api/config_routes.py` |
| 18 | 213 | 26.3% | 76/289 | `services/risk_manager.py` |
| 19 | 195 | 32.3% | 93/288 | `services/backtesting_service.py` |
| 20 | 181 | 0.0% | 0/181 | `core/continuous_monitoring.py` |
| 21 | 178 | 0.0% | 0/178 | `services/auto_rebalancer.py` |
| 22 | 178 | 0.0% | 0/178 | `core/testing_system.py` |
| 23 | 165 | 0.0% | 0/165 | `api/optimized_routes.py` |
| 24 | 164 | 0.0% | 0/164 | `core/paper_trading.py` |
| 25 | 162 | 40.7% | 111/273 | `api/trade.py` |
| 26 | 159 | 0.0% | 0/159 | `core/metrics_manager.py` |
| 27 | 153 | 0.0% | 0/153 | `services/strategy_factory.py` |
| 28 | 152 | 0.0% | 0/152 | `core/error_handler.py` |
| 29 | 137 | 0.0% | 0/137 | `api/strategy_routes.py` |
| 30 | 112 | 0.0% | 0/112 | `services/binance_trades_pnl.py` |
| 31 | 109 | 0.0% | 0/109 | `core/performance_utils.py` |
| 32 | 106 | 56.9% | 140/246 | `core/operation_tracker.py` |
| 33 | 106 | 25.4% | 36/142 | `core/redis_cache.py` |
| 34 | 104 | 0.0% | 0/104 | `core/circuit_breaker.py` |
| 35 | 103 | 14.2% | 17/120 | `services/fund_manager.py` |
| 36 | 101 | 22.3% | 29/130 | `api/metrics.py` |
| 37 | 91 | 20.9% | 24/115 | `api/metrics_routes.py` |
| 38 | 87 | 61.7% | 140/227 | `core/metrics.py` |
| 39 | 87 | 0.0% | 0/87 | `core/safety_validator.py` |
| 40 | 85 | 0.0% | 0/85 | `services/min_qty_updater.py` |
| 41 | 85 | 0.0% | 0/85 | `services/adaptive_grid_engine.py` |
| 42 | 83 | 32.0% | 39/122 | `core/monitoring.py` |
| 43 | 75 | 43.6% | 58/133 | `core/unified_config.py` |
| 44 | 72 | 40.0% | 48/120 | `services/binance_credentials.py` |
| 45 | 72 | 27.3% | 27/99 | `api/binance_sync_routes.py` |
| 46 | 68 | 24.4% | 22/90 | `services/balance_service.py` |
| 47 | 66 | 57.7% | 90/156 | `services/portfolio_snapshot_service.py` |
| 48 | 66 | 36.5% | 38/104 | `api/portfolio_routes.py` |
| 49 | 66 | 30.5% | 29/95 | `services/risk_metrics_engine.py` |
| 50 | 63 | 76.7% | 207/270 | `core/desk_hourly_status.py` |

## COV-0.2 — ignores propuestos

**Skip en este PR:** no hay módulos *claramente* muertos sin riesgo de ocultar paths de riesgo.

Candidatos diferidos (requieren OK de EM, **no** aplicados a `codecov.yml`):

| Path | Motivo tentativo | Acción |
|------|------------------|--------|
| `core/testing_system.py` (178 miss, 0%) | harness legacy de “testing system” en runtime | auditar imports; si cero callers prod → ignore |
| `services/hybrid_ml_engine.py` (370 miss, 0%) | ya DEFER en brief (COV-3.8) | no ignore hasta decisión quant |
| `scripts/archive/**` | ya ignorado | — |

**Prohibido ignore:** `api/**`, `core/circuit_breakers*`, `core/order_execution_guard.py`, `core/live_gate.py`, `core/trading_mode.py`.

## Críticos Wave 1.1

| Módulo | Cover baseline | Cover post COV-1.1 | Target |
|--------|---------------:|-------------------:|-------:|
| `core/trading_mode.py` | 100% | **100%** | ≥90% |
| `core/live_gate.py` | 89.1% | **100%** | ≥90% |
| `core/order_execution_guard.py` | 93.3% | **100%** | ≥90% |

Medición: `pytest tests/test_trading_mode.py tests/test_live_gate.py tests/test_order_execution_guard.py tests/test_paper_cov_fixtures.py --cov=app.core.{trading_mode,live_gate,order_execution_guard}` · 72 passed · paper-only.

