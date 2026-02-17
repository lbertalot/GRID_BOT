# INVARIANTS.md — Reglas Verificables de GridBot v2.5

> Última sincronización con código: 2026-02-17
> Estas invariantes NUNCA deben violarse. Cualquier violación es un bug crítico.

---

## 1. Invariantes Financieras

### INV-F01: Prohibición de float para cálculos monetarios
**Regla**: Todo cálculo de precio, cantidad y notional que interactúa con el exchange DEBE usar `Decimal`.
**Verificado en**: `app/services/order_validation.py` (líneas 58-72), `app/services/trade_executor.py` (línea 9: `from decimal import Decimal`), `app/core/paper_trading.py` (línea 12).
**Excepción conocida**: `app/models/trade.py` usa `Column(Float)` para `quantity`, `entry_price`, `exit_price`, `profit_loss`. **RIESGO**: Pérdida de precisión en persistencia.

### INV-F02: Validación obligatoria pre-orden
**Regla**: Toda orden DEBE pasar por validación de PRICE_FILTER (tickSize), LOT_SIZE (stepSize, minQty, maxQty) y MIN_NOTIONAL antes de enviarse al exchange.
**Verificado en**: `app/services/order_validation.py` → `validate_order_parameters()`.

### INV-F03: Notional mínimo
**Regla**: `cantidad_ajustada × precio >= min_notional` del exchange. Si no se cumple, la orden DEBE rechazarse.
**Verificado en**: `app/services/order_validation.py` líneas 174-175.
**Parámetro en trading_tasks.py**: `MIN_NOTIONAL_USDT = 10.5`.

### INV-F04: Balance suficiente antes de operar
**Regla**: Verificar balance disponible antes de enviar cualquier orden al exchange.
**Verificado en**: `app/services/trading_tasks.py` → `SAFE_MIN_USDT = 15.0`.

### INV-F05: Kelly fraccional con topes
**Regla**: El sizing con Kelly fraccional DEBE estar limitado por:
- `cap_symbol_pct` (default 20% por símbolo)
- `cap_equity_pct` (default 80% del equity)
- `cap_daily_loss_pct` (default 5% pérdida diaria)
- Multiplicador de régimen de mercado (0.5 a 1.0)
**Verificado en**: `app/core/risk_manager.py` → `_apply_position_limits()`.

### INV-F06: Fallback seguro en sizing
**Regla**: Si el cálculo de Kelly falla, el sizing DEBE retornar `account_equity × 0.01` (1% mínimo).
**Verificado en**: `app/core/risk_manager.py` línea 184.

---

## 2. Invariantes de Reconciliación

### INV-R01: Cadencia de reconciliación
**Regla**: La reconciliación contra Binance DEBE ejecutarse cada ≤ 60 segundos.
**Verificado en**: `app/main.py` línea 188: `recon.start(interval_seconds=60)`.

### INV-R02: Activación de breaker por discrepancia
**Regla**: Si la discrepancia de balance supera el umbral relativo (`threshold_pct`, default 1%), el breaker `system_integrity` DEBE activarse.
**Verificado en**: `app/services/reconciliation_service.py` líneas 91-92.
**Nota**: Actualmente `has_internal_accounting = False`, por lo que la activación automática está deshabilitada cuando no hay contabilidad interna separada.

### INV-R03: Métricas de reconciliación
**Regla**: Cada ciclo de reconciliación DEBE emitir:
- `reconciliation_latency_seconds` (Histogram)
- `balance_discrepancy_usd` (Gauge)
- `unaccounted_pnl_usd` (Gauge)
**Verificado en**: `app/services/reconciliation_service.py` líneas 84-95.

---

## 3. Invariantes de Circuit Breakers

### INV-CB01: Tipos registrados
**Regla**: Los únicos circuit breakers válidos son: `balance_discrepancy`, `operation_failure_rate`, `system_integrity`, `critical_mode`.
**Verificado en**: `app/core/circuit_breakers.py` líneas 18-23.

### INV-CB02: Trading detenido con breaker activo
**Regla**: Si CUALQUIER breaker está activo, `is_trading_halted()` DEBE retornar `True`.
**Verificado en**: `app/core/circuit_breakers.py` línea 132.

### INV-CB03: IntegrityGuard bloquea escrituras
**Regla**: El middleware IntegrityGuardMiddleware DEBE bloquear POST/PUT/DELETE en `/api/trade` y `/api/strategies` cuando hay breakers activos (retorna HTTP 503).
**Verificado en**: `app/core/middleware/integrity_guard.py` líneas 39-52.

### INV-CB04: Cooldown anti-flapping
**Regla**: No se puede reactivar un breaker dentro del período de cooldown (`CB_COOLDOWN_SECONDS`, default 300s).
**Verificado en**: `app/core/circuit_breakers.py` líneas 43-47.

### INV-CB05: Métricas de breaker
**Regla**: Al activar/desactivar un breaker, DEBE actualizarse `breaker_state` gauge (0/1).
**Verificado en**: `app/core/circuit_breakers.py` líneas 54-58 y 77-81.

---

## 4. Invariantes de Idempotencia

### INV-I01: client_order_id para exchange
**Regla**: Toda interacción de órdenes con Binance DEBE usar `client_order_id` para garantizar idempotencia.
**Estado**: Documentado como requerimiento en AGENTS.md y .cursorrules. Verificar implementación en trade_executor.py.

### INV-I02: Lock distribuido para tasks
**Regla**: Los Celery tasks críticos DEBEN usar `@with_distributed_lock` para prevenir ejecuciones concurrentes.
**Verificado en**: `app/core/distributed_lock.py` — decorador disponible.
**Usado en**: `app/services/trading_tasks.py` (import verificado, línea 33).

---

## 5. Invariantes de Autenticación

### INV-A01: Endpoints protegidos
**Regla**: Los endpoints de trading, estrategias, configuración y datos sensibles DEBEN requerir autenticación Bearer token.
**Verificado en**: `app/core/auth.py` → `require_auth` dependency.

### INV-A02: Formato de autenticación
**Regla**: El header DEBE ser `Authorization: Bearer <token>`. Ausencia o formato incorrecto → HTTP 401.
**Verificado en**: `app/core/auth.py` líneas 6-21.

---

## 6. Invariantes de Observabilidad

### INV-O01: Métricas Prometheus expuestas
**Regla**: `GET /metrics` DEBE retornar métricas en formato Prometheus text.
**Verificado en**: `app/api/prometheus.py` (incluido en main.py).

### INV-O02: Prefijo de métricas
**Regla**: Métricas clave DEBEN usar prefijo `gridbot_` para namespace consistente.
**Verificado en**: `app/core/metrics.py` → `gridbot_orders_total`, `gridbot_volume_total`, `gridbot_api_requests_total`, `gridbot_profit_loss`.

### INV-O03: Latencia HTTP
**Regla**: `api_request_duration_seconds` DEBE registrarse para toda request.
**Verificado en**: `app/core/middleware/prometheus_http.py` (middleware activo en main.py).

---

## 7. Invariantes de ML

### INV-ML01: Fallback seguro
**Regla**: Si el modelo ML no está disponible o falla, el sistema DEBE retornar predicción por defecto: `RegimePrediction(label=0, proba=0.5)` (MLEngine) o `RANGE con conf=0.5` (HybridMLEngine).
**Verificado en**: `app/services/ml_engine.py` línea 192, `app/services/hybrid_ml_engine.py` líneas 582-588.

### INV-ML02: No bloquear event loop
**Regla**: Operaciones I/O pesadas de ML DEBEN usar `asyncio.to_thread()`.
**Verificado en**: `app/services/ml_engine.py` línea 95: `await asyncio.to_thread(joblib.dump, ...)`.

### INV-ML03: Emergency stop prevalece
**Regla**: Si `RiskManager.emergency_stop == True`, el StrategySelector DEBE retornar HOLD independientemente de la predicción ML.
**Verificado en**: `app/services/strategy_selector.py` líneas 286-293.

---

## 8. Invariantes de Configuración

### INV-C01: Secretos fuera del código
**Regla**: `BINANCE_API_KEY`, `BINANCE_SECRET_KEY`, `SECRET_KEY`, `DATABASE_URL` NUNCA deben estar en el código fuente ni en logs.
**Verificado en**: `.gitignore` (incluye .env).

### INV-C02: Validación de producción
**Regla**: En `ENV=production`, `SECRET_KEY` es obligatorio y `DEBUG` debe ser `false`.
**Verificado en**: `app/core/config.py` líneas 67-70.

---

## 9. Invariantes de Concurrencia

### INV-CC01: Métricas de conflicto
**Regla**: Los conflictos de actualización de balance DEBEN registrarse en `balance_update_conflicts_total`.
**Verificado en**: `app/core/metrics.py` líneas 654-658.

### INV-CC02: Métricas de lock distribuido
**Regla**: Adquisiciones, omisiones y errores de locks distribuidos DEBEN registrarse en métricas Prometheus.
**Verificado en**: `app/core/metrics.py` líneas 661-684.

---

## 10. Riesgos Conocidos

| ID | Riesgo | Severidad | Detalle |
|---|---|---|---|
| RISK-01 | Float en modelo Trade | Media | `app/models/trade.py` usa `Column(Float)` para precios y cantidades. Posible pérdida de precisión en persistencia. |
| RISK-02 | Reconciliación sin contabilidad interna | Baja | `has_internal_accounting = False` en reconciliation_service.py: breaker por discrepancia no se activa automáticamente. |
| RISK-03 | get_strategy_history no implementado | Baja | `app/services/strategy_selector.py` línea 464: retorna lista vacía. |
| RISK-04 | get_strategy_performance no implementado | Baja | `app/services/strategy_selector.py` línea 479: retorna datos vacíos. |
