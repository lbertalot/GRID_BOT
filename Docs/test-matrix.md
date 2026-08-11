# Test matrix — GRID_BOT (S-COV-85 baseline)

> **Baseline documentada = Codecov/CI main** · actualizado **2026-08-10**  
> HEAD ref: post-#122 (COV-5.9) · CI TOTAL **~83.52%** · `COVERAGE_FAIL_UNDER=80` · Codecov project **target 85%** (threshold 7%)  
> Referencias: [`TESTING_RULES.md`](../TESTING_RULES.md) · [`CICD_RUNBOOK.md`](CICD_RUNBOOK.md) · monorepo `Docs/engineering/test-matrix.md` · rule `30-tdd-trading` · **PROMOTE_LIVE: NO**

## Gates activos

| Gate | Valor | Dónde |
|------|-------|-------|
| Pytest CI | `--cov-fail-under=80` | `.github/workflows/ci.yml` |
| Codecov project | target **85%**, threshold **7%**, blocking | `codecov.yml` |
| Codecov patch | target **50%**, blocking | `codecov.yml` |
| Live / órdenes reales | Prohibido en CI | rule `40-no-live-without-gate` |

## Matriz por capa

| Capa | Qué | Paths / suites | P0 |
|------|-----|----------------|----|
| Unit mode/gate | `effective_mode`, order guard, live gate | `tests/test_trading_mode.py`, `tests/test_order_execution_guard.py`, `tests/unit/test_cov_1_1_*`, `test_cov_2_1_*` | Sí |
| Unit risk/breakers | Circuit breakers, capital, desk remediate | `tests/test_circuit_breakers*.py`, `tests/unit/test_cov_1_2_*`, `test_cov_1_3_*`, `test_cov_3_6_*` | Sí |
| Unit paper ledger | Equity ledger / IC / paper execute | `tests/unit/test_cov_1_4_*`, `test_cov_1_6_*` | Sí |
| Unit validators | Balance / integrity / safety | `tests/unit/test_cov_1_5_*` | Sí |
| Unit API | Trade / config / desk / metrics / sync | `tests/unit/test_cov_2_2_*` … `test_cov_2_6_*` | Sí |
| Unit Binance stack | Service / async / sync / stream (mocks) | `tests/unit/test_cov_3_1_*`, `test_cov_3_3_*` | Sí |
| Unit execution | Executor / validation / commission | `tests/unit/test_cov_3_4_*` | Sí |
| Unit scheduler | `grid_job` / scheduler / config | `tests/unit/test_cov_3_5_*` | Sí |
| Unit metrics read | metrics_service / manager / analyzer | `tests/unit/test_cov_3_7_*` | Sí |
| Unit residual | fund_manager / rebalancer_v2 / tasks | `tests/unit/test_cov_4_1_*` | Sí |
| Unit main/mw | lifespan paper + security middleware | `tests/unit/test_cov_4_2_*` | Sí |
| QAA | Filtros, Decimal, breakers, Kelly, recon | `tests/test_qaa_*.py` | Sí |
| Contract health | `/health`, `/health/trading-mode`, paper flags | `tests/unit/test_cov_2_1_*`, system routes | Sí |
| Integration paper | TestClient + `paper_env` (sin red Binance) | fixtures `tests/fixtures/paper_cov.py` | Sí |
| E2E HTTP localhost | Suite `_E2E_TEST_FILES` en `conftest.py` | skip en `CI=true` | No en CI |
| Drift skip | `_BROKEN_PREEXISTING_TEST_FILES` | deuda; no ampliar | No |
| Live | Órdenes reales / FORCE_REAL_MODE | **Nunca en CI** | Nunca auto |

## Comando paper-safe (orientativo)

```bash
cd GRID_BOT
export PAPER_TRADING=true FORCE_REAL_MODE=false TRADING_ENABLED=false \
       USE_REAL_BINANCE=0 CI=true EMERGENCY_STOP=true CB_SHARED_STORE=memory
python3.11 -m pytest tests/unit/ -q --tb=line
# Suite CI (gate 80):
# python3.11 -m pytest tests/ -q --cov=app --cov-fail-under=80
```

## Residual hacia 85%

| Ítem | Notas |
|------|-------|
| CI pytest 70→80→85 | Solo con TOTAL ≥ umbral + margen (COV-4.3 restante) |
| Codecov threshold 7%→1–2% | Cuando main sostenga ≥85% estable |
| COV-3.8 hybrid_ml | **defer** |
| Drift `_BROKEN_*` | PR dedicado; no chase pp |
| Meta sprint S1 | Codecov main **≥85%** (aún ~78%) |
