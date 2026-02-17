# Matriz de Riesgo QAA - GridBot v2.5

## Resumen Ejecutivo

Fecha de auditoría: 2026-02-17
Auditor: QAA Agent (Quality Assurance Automation)
Versión del sistema: GridBot v2.5

### Estadísticas Generales
- Módulos analizados: 15+
- Tests QAA creados: ~150+
- Hallazgos críticos: 6
- Hallazgos altos: 5
- Hallazgos medios: 4

---

## Hallazgos Críticos

### 1. Reconciliación Siempre Reporta Discrepancia = 0
- **Archivo**: `app/services/reconciliation_service.py` líneas 76-82
- **Nivel**: 🔴 CRÍTICO
- **Descripción**: `int_total_value = total_value` y `discrepancy = 0.0` hacen que la reconciliación NUNCA detecte discrepancias reales. `has_internal_accounting = False` desactiva permanentemente el breaker.
- **Impacto financiero**: Pérdida de capital no detectada. El sistema opera ciego ante discrepancias entre estado interno y Binance.
- **Fix propuesto**: Implementar contabilidad interna independiente (tabla de balances internos) y comparar contra Binance.
- **Test de regresión**: `test_qaa_reconciliation_idempotency.py::TestReconciliationNullDiscrepancy`

### 2. TradeExecutor NO Verifica Circuit Breakers
- **Archivo**: `app/services/trade_executor.py` línea 55+
- **Nivel**: 🔴 CRÍTICO
- **Descripción**: `execute_order()` NO verifica `CircuitBreakers.is_trading_halted()` ni `RiskManager.emergency_stop` antes de enviar órdenes a Binance.
- **Impacto financiero**: Órdenes se ejecutan durante condiciones de emergencia, flash crash, o discrepancias de balance.
- **Fix propuesto**: Agregar guard clause al inicio de `execute_order`:
  ```python
  if circuit_breakers.is_trading_halted():
      raise TradingHaltedError("Circuit breaker activo")
  ```
- **Test de regresión**: `test_qaa_circuit_breakers.py::TestBreakerTradeExecutorIntegration`

### 3. TradeExecutor NO Usa client_order_id (Idempotencia)
- **Archivo**: `app/services/trade_executor.py` líneas 61-67
- **Nivel**: 🔴 CRÍTICO
- **Descripción**: `create_order()` no genera `newClientOrderId`. El retry por error -1021 puede ejecutar la orden DOS VECES si el primer request se completó pero el response se perdió.
- **Impacto financiero**: Ejecución duplicada de órdenes → doble exposición no deseada.
- **Fix propuesto**: Generar UUID como `newClientOrderId` y persistirlo antes de enviar.
- **Test de regresión**: `test_qaa_reconciliation_idempotency.py::TestOrderIdempotency`

### 4. Uso de float() en Cálculos Financieros
- **Archivos**: `order_validation.py` (líneas 40-49), `precision.py` (líneas 59-80), `reconciliation_service.py` (línea 46)
- **Nivel**: 🔴 CRÍTICO
- **Descripción**: Los filtros del exchange (stepSize, tickSize, minNotional) se convierten a float, perdiendo precisión. `precision.py` usa `int(price/tick)` en lugar de Decimal.
- **Impacto financiero**: Errores de redondeo acumulativos, cálculos de notional incorrectos, rechazo de órdenes.
- **Fix propuesto**: Usar `Decimal(str(value))` en todos los cálculos financieros.
- **Test de regresión**: `test_qaa_decimal_precision.py::TestStaticFloatAudit`

### 5. TradeExecutor Hardcodea Quote Asset de 4 Caracteres
- **Archivo**: `app/services/trade_executor.py` línea 187
- **Nivel**: 🔴 CRÍTICO
- **Descripción**: `base_asset = symbol[:-4]` asume que el quote asset siempre tiene 4 caracteres (USDT). Falla para pares como ETHBTC, BTCEUR, etc.
- **Impacto financiero**: Balances internos se actualizan con activos incorrectos.
- **Fix propuesto**: Usar `exchange_info['baseAsset']` y `exchange_info['quoteAsset']`.
- **Test de regresión**: `test_qaa_decimal_precision.py::TestTradeExecutorAssetParsing`

### 6. apply_market_regime_filter Reduce Exposición Acumulativamente
- **Archivo**: `app/core/risk_manager.py` líneas 337-344
- **Nivel**: 🔴 CRÍTICO
- **Descripción**: `self.max_total_exposure_pct *= 0.5` y `self.min_profit_bps *= 2` se aplican cada vez que se llama con regímenes negativos, sin restaurar al valor original. Después de 5 llamadas: exposure = 0.80 * 0.5^5 = 0.025 (2.5%), profit_bps = 50 * 2^5 = 1600 bps (16%).
- **Impacto financiero**: El bot se vuelve incapaz de operar, incluso cuando el mercado mejora.
- **Fix propuesto**: Calcular el multiplicador desde el valor original, no acumularlo:
  ```python
  self.max_total_exposure_pct = self._original_max_exposure * multiplier
  ```
- **Test de regresión**: `test_qaa_kelly_sizing.py::TestRegimeFilterAccumulation`

---

## Hallazgos Altos

### 7. Circuit Breaker Cooldown Puede Bloquear Activación Legítima
- **Archivo**: `app/core/circuit_breakers.py` líneas 43-47
- **Nivel**: 🟠 ALTO
- **Descripción**: Si un breaker se activa y desactiva, una nueva emergencia dentro del cooldown (5 min) es ignorada.
- **Impacto**: Periodo de trading sin protección después de una primera alerta.
- **Fix propuesto**: Diferenciar entre re-activación por flapping y emergencia real.
- **Test**: `test_qaa_circuit_breakers.py::TestCooldownBehavior`

### 8. Singleton Global de TradeExecutor Sin Protección Thread-Safe
- **Archivo**: `app/services/trade_executor.py` línea 255
- **Nivel**: 🟠 ALTO
- **Descripción**: `trade_executor = TradeExecutor()` es un singleton global sin mutex. Múltiples coroutines pueden ejecutar órdenes simultáneamente sin coordinación.
- **Test**: `test_qaa_race_conditions.py::TestSingletonRaceConditions`

### 9. OrderValidator Cache Sin Thread-Safety
- **Archivo**: `app/services/order_validation.py` línea 17
- **Nivel**: 🟠 ALTO
- **Descripción**: `_symbol_info_cache` es un dict sin protección de concurrencia.
- **Test**: `test_qaa_race_conditions.py::TestSingletonRaceConditions`

### 10. CircuitBreakers Usa Dict No Persistente
- **Archivo**: `app/core/circuit_breakers.py`
- **Nivel**: 🟠 ALTO
- **Descripción**: Estado de breakers en memoria se pierde al reiniciar. Si el bot crashea durante una emergencia, el restart no tendrá los breakers activos.
- **Fix propuesto**: Persistir estado en Redis o PostgreSQL.

### 11. RiskManager No Integrado con CircuitBreakers
- **Nivel**: 🟠 ALTO
- **Descripción**: `RiskManager.emergency_stop` y `CircuitBreakers` son sistemas independientes. Una activación en uno no se refleja en el otro.
- **Fix propuesto**: Unificar la interfaz de breakers.

---

## Hallazgos Medios

### 12. MLEngine Fallback Silencioso
- **Archivo**: `app/services/ml_engine.py`
- **Nivel**: 🟡 MEDIO
- **Descripción**: Si River no está instalado, MLEngine opera en "modo no operativo" pero no emite alerta visible al operador.

### 13. Grid Action Puede Sugerir SELL en Gap Bajista
- **Archivo**: `app/services/grid_strategy.py`
- **Nivel**: 🟡 MEDIO
- **Descripción**: `decide_grid_action` puede sugerir SELL si el precio cae dentro de la tolerancia de un nivel de grid, amplificando pérdidas.

### 14. StrategySelector Usa Float para Sizing
- **Archivo**: `app/services/strategy_selector.py`
- **Nivel**: 🟡 MEDIO
- **Descripción**: `order_size_usdt`, `tranche_size` etc. son float en lugar de Decimal.

### 15. Confidence Multipliers Son Números Mágicos
- **Archivo**: `app/services/strategy_selector.py` líneas 323-326
- **Nivel**: 🟡 MEDIO
- **Descripción**: `confidence *= 0.69` y `confidence *= 0.49` sin documentación del razonamiento.

---

## Priorización de Fixes

| Prioridad | Hallazgo | Esfuerzo | Impacto |
|-----------|----------|----------|---------|
| P0 | #2 TradeExecutor sin breaker check | Bajo | Crítico |
| P0 | #3 TradeExecutor sin client_order_id | Bajo | Crítico |
| P0 | #1 Reconciliación nula | Medio | Crítico |
| P1 | #4 float() en cálculos financieros | Alto | Crítico |
| P1 | #5 Hardcoded quote asset 4 chars | Bajo | Crítico |
| P1 | #6 apply_market_regime_filter acumulativo | Bajo | Crítico |
| P2 | #7 Cooldown bloquea activación legítima | Medio | Alto |
| P2 | #8 Singleton sin thread-safety | Medio | Alto |
| P3 | #10 Breakers no persistentes | Medio | Alto |
| P3 | #12-15 Hallazgos medios | Variable | Medio |

---

## Cobertura de Tests QAA

| Archivo de Test | Tests | Área |
|----------------|-------|------|
| test_qaa_binance_filters.py | ~35 | Filtros Binance, LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL |
| test_qaa_decimal_precision.py | ~25 | Precisión Decimal, auditoría float, asset parsing |
| test_qaa_circuit_breakers.py | ~25 | Circuit breakers, modo crítico, cooldown, integración |
| test_qaa_kelly_sizing.py | ~30 | Kelly fraccional, límites de posición, trailing stops |
| test_qaa_strategy_selector_ml.py | ~30 | StrategySelector, ML fallback, confidence |
| test_qaa_reconciliation_idempotency.py | ~20 | Reconciliación, idempotencia, PnL |
| test_qaa_chaos_resilience.py | ~25 | Flash crash, desconexión, respuestas inconsistentes |
| test_qaa_race_conditions.py | ~15 | Race conditions, concurrencia, locks |
| **TOTAL** | **~205** | |
