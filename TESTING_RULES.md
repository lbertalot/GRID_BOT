# TESTING_RULES.md — Reglas de Testing de GridBot v2.5

> Última sincronización con código: **2026-08-10** (S-COV-85 Wave 4)  
> Suite: `tests/` + `tests/unit/test_cov_*` · matriz: [`Docs/test-matrix.md`](Docs/test-matrix.md)  
> Baseline cobertura = **Codecov/CI main ~78.33%** · gate pytest **70** · meta **85%** · **PROMOTE_LIVE: NO**

---

## 1. Qué Bloquea un PR

Un PR DEBE ser rechazado si:

1. **Tests fallan**: `pytest -q` no pasa con exit code 0.
2. **Cobertura insuficiente**: Cobertura global < 85% en módulos críticos.
3. **Secretos en código**: Cualquier API key, secret o token hardcodeado.
4. **Float en cálculos monetarios**: Uso de `float` para precios/cantidades en lógica de órdenes.
5. **Validación ausente**: Nuevo endpoint de trading sin validación de exchange filters.
6. **Métricas Prometheus ausentes**: Nuevo flujo crítico sin instrumentación.
7. **Breaker bypass**: Operación de trading que no consulta circuit breakers.
8. **Test de regresión faltante**: Cambio en módulo crítico sin test correspondiente.

---

## 2. Regresiones Críticas

Estas regresiones NUNCA deben ocurrir. Si se detecta cualquiera, es un bug P0:

| ID | Regresión | Test que la cubre |
|---|---|---|
| REG-01 | Orden enviada sin validar LOT_SIZE/PRICE_FILTER | `test_qaa_binance_filters.py` |
| REG-02 | Orden con notional < minNotional | `test_qaa_binance_filters.py` |
| REG-03 | Pérdida de precisión Decimal en precios | `test_qaa_decimal_precision.py` |
| REG-04 | Circuit breaker no bloquea trading | `test_qaa_circuit_breakers.py` |
| REG-05 | Reconciliación con discrepancia no detectada | `test_qaa_reconciliation_idempotency.py` |
| REG-06 | Kelly sizing sin caps aplicados | `test_qaa_kelly_sizing.py` |
| REG-07 | StrategySelector sin fallback ML | `test_qaa_strategy_selector_ml.py` |
| REG-08 | Race condition en balances | `test_qaa_race_conditions.py` |
| REG-09 | Endpoint protegido accesible sin auth | `test_authentication.py`, `test_authentication_simple.py` |
| REG-10 | Métricas Prometheus no expuestas | `test_metrics.py`, `test_prometheus_middleware.py` |

---

## 3. Requisitos Mínimos de Cobertura

| Módulo | Cobertura Mínima | Justificación |
|---|---|---|
| `app/core/circuit_breakers.py` | 90% | Seguridad de capital |
| `app/core/risk_manager.py` | 85% | Sizing y control de riesgo |
| `app/services/order_validation.py` | 90% | Validación pre-orden |
| `app/services/reconciliation_service.py` | 80% | Integridad financiera |
| `app/services/strategy_selector.py` | 85% | Selección de estrategia |
| `app/services/trade_executor.py` | 80% | Ejecución de órdenes |
| `app/services/ml_engine.py` | 75% | Motor ML con fallback |
| `app/core/auth.py` | 95% | Autenticación |
| `app/core/middleware/integrity_guard.py` | 90% | Bloqueo por breakers |
| `app/schemas/validation.py` | 85% | Validación de inputs |

---

## 4. Tests Obligatorios por Módulo

### 4.1 Circuit Breakers
- **Archivo**: `tests/test_circuit_breakers.py`, `tests/test_qaa_circuit_breakers.py`
- Tests obligatorios:
  - Activar/desactivar cada tipo de breaker.
  - Verificar `is_trading_halted()` con breakers activos.
  - Verificar cooldown anti-flapping.
  - Verificar modo crítico activa todos.
  - Verificar que métricas Prometheus se actualizan.

### 4.2 Order Validation
- **Archivo**: `tests/test_order_validation_rules.py`, `tests/test_qaa_binance_filters.py`
- Tests obligatorios:
  - Validar stepSize rounding.
  - Validar tickSize rounding para LIMIT.
  - Rechazar cantidad < minQty.
  - Rechazar notional < minNotional.
  - Rechazar precio fuera de rango.
  - Verificar Decimal vs float en cálculos.

### 4.3 Risk Manager / Kelly Sizing
- **Archivo**: `tests/test_risk_manager_v2.py`, `tests/test_qaa_kelly_sizing.py`
- Tests obligatorios:
  - Kelly fraccional produce resultado correcto.
  - Caps se aplican (symbol, equity, daily loss).
  - Multiplicador de régimen se aplica.
  - Fallback a ATR sizing cuando Kelly no aplica.
  - Fallback a 1% si todo falla.
  - Emergency stop detiene trading.

### 4.4 Strategy Selector
- **Archivo**: `tests/test_strategy_selector.py`, `tests/test_qaa_strategy_selector_ml.py`
- Tests obligatorios:
  - Cada combinación (régimen, volatilidad) → estrategia correcta.
  - Emergency stop → HOLD.
  - Fallback si no hay config → HOLD.
  - Confianza ajustada por risk_score y daily_pnl.
  - Métricas Prometheus actualizadas.

### 4.5 Reconciliación
- **Archivo**: `tests/test_qaa_reconciliation_idempotency.py`
- Tests obligatorios:
  - Ciclo completo produce resultado válido.
  - Métricas de latencia emitidas.
  - Breaker activado si discrepancia > umbral (cuando aplique).
  - Idempotencia del loop (no inicia doble).

### 4.6 ML Engine
- **Archivo**: `tests/test_ml_engine.py`
- Tests obligatorios:
  - Predicción retorna RegimePrediction válido.
  - Fallback cuando pipeline es None.
  - Features extraídas correctamente de klines.
  - Entrenamiento incremental no lanza excepciones.

### 4.7 Autenticación
- **Archivo**: `tests/test_authentication.py`, `tests/test_authentication_simple.py`, `tests/test_auth_working.py`
- Tests obligatorios:
  - Request sin header → 401.
  - Request con formato incorrecto → 401.
  - Request con token inválido → 401.
  - Request con token válido → 200.

### 4.8 Precisión Decimal
- **Archivo**: `tests/test_decimal_validation.py`, `tests/test_qaa_decimal_precision.py`
- Tests obligatorios:
  - Cálculos de notional usan Decimal internamente.
  - No hay pérdida de precisión en redondeo step/tick.

### 4.9 Trading Cycle
- **Archivo**: `tests/test_trading_cycle.py`, `tests/test_trading_cycle_tick.py`
- Tests obligatorios:
  - Ciclo completo ejecutable sin errores.
  - Respeta breakers activos.
  - Respeta MIN_NOTIONAL_USDT.

### 4.10 IntegrityGuard Middleware
- **Archivo**: `tests/test_middleware_metrics.py`
- Tests obligatorios:
  - GET requests pasan siempre.
  - POST en rutas protegidas bloqueado con breakers activos.
  - Bypass en entorno de tests.

---

## 5. Convenciones de Testing

### 5.1 Ejecución
```bash
# Suite completa
pytest -q

# Con cobertura
pytest --cov=app --cov-report=term-missing

# Test específico
pytest tests/test_circuit_breakers.py -q

# Solo QAA (Quality Assurance Automation)
pytest tests/test_qaa_*.py -q
```

### 5.2 Configuración (verificado en `pytest.ini`)
```ini
[pytest]
testpaths = tests
asyncio_mode = auto
```

### 5.3 Entorno de Test
- `PAPER_TRADING=true` en tests.
- `BINANCE_TESTNET=true` si se necesitan llamadas reales.
- Usar fixtures/mocks para Binance client (no llamadas reales en CI).
- `INTEGRITY_GUARD_DISABLED=1` o `PYTEST_CURRENT_TEST` para bypass de middleware.

### 5.4 Fixtures Comunes
- Ver `tests/conftest.py` para fixtures compartidas.
- Preferir `httpx.AsyncClient` para tests de API.
- Usar `unittest.mock.patch` para servicios externos.

---

## 6. Tests QAA (Quality Assurance Automation)

Tests prefijados con `test_qaa_*` son tests de aseguramiento de calidad de alto nivel:

| Archivo | Área |
|---|---|
| `test_qaa_reconciliation_idempotency.py` | Reconciliación e idempotencia |
| `test_qaa_kelly_sizing.py` | Kelly fraccional y sizing |
| `test_qaa_race_conditions.py` | Condiciones de carrera |
| `test_qaa_strategy_selector_ml.py` | Selector de estrategia + ML |
| `test_qaa_circuit_breakers.py` | Circuit breakers |
| `test_qaa_chaos_resilience.py` | Resiliencia ante caos |
| `test_qaa_decimal_precision.py` | Precisión decimal |
| `test_qaa_binance_filters.py` | Filtros de Binance |

Estos tests DEBEN pasar siempre. Son la línea de defensa contra regresiones críticas.

---

## 7. Deuda de Testing — Estado real (actualizado 2026-08-10)

### 7.1 Resuelto — FASE 3 P1 + S-COV-85 (extracto)

| Módulo | Antes | Después (aprox.) | Suite |
|---|---|---|---|
| `trade_executor` / validation / commission | parcial | ≥90% unit | `test_*_p1` + `test_cov_3_4_*` |
| `circuit_breakers` / store / routes | parcial | ~100% unit | `test_cov_1_2_*` |
| `desk_auto_remediation` / desk_status_tasks | bajo | ~100% | `test_cov_1_3_*` |
| `paper_equity_ledger` / grid paper | parcial | ≥90% | `test_cov_1_4_*`, `test_cov_1_6_*` |
| `scheduler/grid_job` + config | bajo | ~100% / ≥97% | `test_cov_3_5_*` |
| `metrics_service` + read paths | parcial | ~99% | `test_cov_3_7_*` |
| `fund_manager` / `auto_rebalancer_v2` | bajo | ~97% / ~83% | `test_cov_4_1_*` |
| `main` lifespan + security middleware | parcial | ~64% / ~97% | `test_cov_4_2_*` |

> Matriz completa y gates: [`Docs/test-matrix.md`](Docs/test-matrix.md).  
> Verificación orientativa CI: `Required test coverage of 70% reached. Total coverage: 78.33%` (main 2026-08-10).

### 7.2 Deuda diferida — planificada

| Módulo | Estado | Prioridad | Plan |
|---|---|---|---|
| `HybridMLEngine` / backtest stubs | Sin TF en CI | Media | **COV-3.8 defer** |
| Drift `_BROKEN_PREEXISTING_TEST_FILES` | skip en CI | Media | PR dedicado (no chase pp) |
| E2E `_E2E_TEST_FILES` | skip en CI | Baja | Solo con API local |
| Escalera pytest 70→80→85 | Gate 70 | P0 S-COV | Subir con margen TOTAL |
| Codecov threshold 7% | Meta 85% | P0 | Bajar threshold al ≥85% estable |
| `strategy_selector` history/perf TODOs | No impl. | Baja | Implementación + test |

### 7.3 Drift de tests pre-existentes

`tests/conftest.py` mantiene `_BROKEN_PREEXISTING_TEST_FILES` (skip en `CI=true`).
No ampliar la lista en PRs de cobertura; cada salida de la lista exige fixtures al día.

### 7.4 Cobertura global — baseline S-COV-85

| Entorno | Baseline 2026-04-26 | **Baseline 2026-08-10** | Gate activo |
|---|---|---|---|
| Local (`python3.11`) | 29.05 % | — | — |
| CI pytest TOTAL | 25.70 % | **~78.33%** (`21438` stmts / miss ~4645) | `--cov-fail-under=70` |
| Codecov project | ~25 % (informational) | **~78.33%** (blocking, target 85%) | `codecov.yml` |

- **Fuente de verdad de baseline docs** = Codecov/CI main (este § + `Docs/test-matrix.md`).
- **Gate CI**: `--cov-fail-under=70` (COV-4.3).
- **Codecov** (COV-4.4): project `target: 85%`, `informational: false`, `threshold: 7%`; patch `50%`.
- **Escalera restante**: pytest 70→80→85; Codecov threshold →1–2% al cruzar 85%.
- Runbook: `Docs/CICD_RUNBOOK.md` · sprint monorepo `Docs/engineering/sprint-S-COV-85-2026-08-09.md`.

### 7.5 Deuda de seguridad (Bandit + pip-audit)

Verificado el 2026-04-26.

#### Bandit
- **HIGH severity**: 0 hallazgos → CI bloqueante OK.
- **MEDIUM severity**: 12 hallazgos conocidos, gate informativo (no bloqueante).
  Plan: documentar cada caso con `# nosec BXXX – justification` y elevar el
  gate a MEDIUM en sprint 2026-06.

| ID Bandit | Cantidad | Descripción | Mitigación actual |
|---|---|---|---|
| B108 | 3 | `hardcoded_tmp_directory` | Paths `/tmp/` legítimos para artefactos efímeros |
| B310 | 3 | `urllib_urlopen` | URLs validadas internamente; no input de usuario |
| B104 | 1 | `bind_all_interfaces` | uvicorn `0.0.0.0` esperado en contenedor |
| B301 | 2 | `pickle` | Datos serializados confiables (cache interno) |

#### pip-audit (CVEs en dependencias)
3 CVEs ignoradas con justificación explícita en `.github/workflows/ci.yml`:

| CVE | Paquete | Versión | Fix | Justificación / Plan |
|---|---|---|---|---|
| GHSA-jfh8-c2jp-5r3q | pip (transitivo) | < 25 | sin upstream patch | No afecta runtime — solo entorno de instalación |
| PYSEC-2024-38 | fastapi | 0.104.1 | 0.109.1 | ReDoS en parser Content-Type. Mitigado por Nginx + WAF. **Upgrade en sprint 2026-05** (validar compat Pydantic v2) |
| CVE-2024-47874 | starlette | 0.27.0 | 0.40.0 | DoS multipart. GridBot no expone multipart sin auth + size cap. **Upgrade en bundle con fastapi 0.109+** |
| CVE-2025-54121 | starlette | 0.27.0 | 0.47.2 | DoS BodyParser. Mismo mitigante (auth + límites Nginx). **Mismo plan upgrade** |

Verificación local:
```bash
pip-audit -r requirements.txt \
  --ignore-vuln GHSA-jfh8-c2jp-5r3q \
  --ignore-vuln PYSEC-2024-38 \
  --ignore-vuln CVE-2024-47874 \
  --ignore-vuln CVE-2025-54121
# → "No known vulnerabilities found, 3 ignored"
```
