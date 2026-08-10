# TESTING_RULES.md — Reglas de Testing de GridBot v2.5

> Última sincronización con código: 2026-02-17
> Suite de tests: `tests/` (63 archivos verificados)

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

## 7. Deuda de Testing — Estado real (actualizado 2026-04-26)

### 7.1 Resuelto en esta iteración (FASE 3 P1)

| Módulo | Estado anterior | Estado actual | Test file |
|---|---|---|---|
| `app/services/trade_executor.py` | Sin tests (skipped por drift) | **87 %** ≥ 80 % objetivo | `tests/test_trade_executor_p1.py` (17 tests) |
| `app/services/reconciliation_service.py` | 21 % (path `has_internal_accounting=False` sin cubrir) | **85 %** ≥ 80 % objetivo | `tests/test_reconciliation_service_p1.py` (13 tests) |
| `app/core/auth.py` | 32 % | **95 %** ≥ 95 % objetivo | `tests/test_auth_p1.py` |
| `app/services/order_validation.py` | 68 % | **92 %** ≥ 90 % objetivo | `tests/test_order_validation_p1.py` |
| `app/core/circuit_breakers.py` | 79 % | **100 %** ≥ 90 % objetivo | `tests/test_circuit_breakers_p1.py` (22 tests) |
| `app/core/risk_manager.py` | 76 % | **96 %** ≥ 85 % objetivo | (cobertura indirecta vía suite QAA) |

> Verificación: `pytest tests/test_qaa_*.py -q` → **170 passed, 0 failed, 25 skipped**.

### 7.2 Deuda diferida — planificada

| Módulo | Estado | Prioridad | Plan |
|---|---|---|---|
| `app/core/middleware/prometheus_http.py` | Sin test directo | Media (P2) | Sprint siguiente — añadir test de instrumentación HTTP |
| `app/core/middleware/security_hardening.py` | Sin test directo | Media (P2) | Sprint siguiente |
| `app/scheduler/grid_job.py` | Sin test directo | Media (P2) | Sprint siguiente |
| `app/scheduler/reconciliation_job.py` | Sin test directo | Media (P2) | Sprint siguiente |
| `app/api/{alert,breakers,risk,portfolio}_routes.py` | Cobertura general baja | Baja (P3) | Backlog — TDD por endpoint |
| `app/services/strategy_factory.py` + `strategies/{base,rsi_macd}.py` | Sin tests específicos | Baja (P3) | Backlog |
| `strategy_selector.get_strategy_history()` | `TODO: NOT IMPLEMENTED` | Baja | Implementación pendiente, no test |
| `strategy_selector.get_strategy_performance()` | `TODO: NOT IMPLEMENTED` | Baja | Implementación pendiente, no test |
| `HybridMLEngine` integración E2E | Sin test E2E | Media | Backlog |
| `auto_rebalancer_v2` | Test parcial | Media | Ampliar `tests/test_auto_rebalancer_v2.py` |

### 7.3 Drift de tests pre-existentes

`tests/conftest.py` mantiene la lista `_BROKEN_PREEXISTING_TEST_FILES` (14 archivos) que se *skipean* por code drift no resuelto. Eliminarlos uno a uno es trabajo de los próximos sprints; cada eliminación de la lista exige rehacer las fixtures y volver a verde.

### 7.4 Cobertura global

| Entorno | Baseline 2026-04-26 | Medido 2026-08-10 | Gate activo |
|---|---|---|---|
| Local (`python3.11`) | 29.05 % | — | — |
| CI (GitHub Actions hosted) | 25.70 % | ~78 % (Codecov/project) | `--cov-fail-under=70` |

El delta histórico ~3.3 pp entre local y CI se debía a diferencias de entorno
(redis/postgres, skips hosted, `sys.path`). Post S-COV-85 Waves 1–4.2 el
TOTAL CI se sitúa ~78 %.

- **Gate CI actual**: `--cov-fail-under=70` (COV-4.3; ver `.github/workflows/ci.yml`).
- **Escalera restante**: 70→80→85 (subir solo con TOTAL ≥ umbral + margen estable).
- **Plan**: documentado en `Docs/CICD_RUNBOOK.md` y sprint `S-COV-85`.

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
