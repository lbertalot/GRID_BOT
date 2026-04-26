# Verificación: GridBot v2.5 en producción (grid-bot-ia-eu)

**Fecha:** 2026-02-17
**App:** https://YOUR-APP-NAME.herokuapp.com/

Este documento cruza la descripción pública de GridBot v2.5 con el código y la configuración en producción.

---

## 1. Descripción general

> *"GridBot v2.5 es un sistema de trading algorítmico automatizado para Binance spot que combina grid trading con machine learning para adaptar la estrategia al régimen de mercado."*

| Afirmación | En código | En producción |
|------------|-----------|----------------|
| Trading algorítmico Binance spot | Sí: `binance_service`, `trade_executor`, `trading_tasks`, órdenes vía python-binance | App EU con proxy QuotaGuard; Binance API key configurada |
| Grid trading | Sí: `optimized_grid_manager`, grid config, niveles | Config y scheduler desplegados |
| ML para régimen de mercado | Sí: `hybrid_ml_engine` (LSTM/Transformer + River), `ml_engine` (River), `strategy_selector` usa `RegimePrediction` | `ML_ENABLED=false` en prod; se usa **fallback estático** (RANGE por defecto) |

---

## 2. Qué hace

> *"Opera automáticamente en Binance (paper o real), con sizing por Kelly fraccional, circuit breakers y validación estricta de filtros del exchange (precio, tamaño de lote, notional)."*

| Componente | Ubicación en código | Producción |
|------------|---------------------|------------|
| Paper / real | `PAPER_TRADING`, `FORCE_REAL_MODE` en `binance_service`, `config` | `PAPER_TRADING=false`, `TRADING_ENABLED=true` → modo **real** |
| Sizing Kelly fraccional | `app/core/risk_manager.py`: `KellyParams`, `_calculate_kelly_position_size`, `fractional_kelly`; `strategy_selector` usa Kelly para tamaño de orden | Risk manager y strategy selector en uso en ciclo de trading |
| Circuit breakers | `app/core/circuit_breakers.py`: `CircuitBreakers`, activación por `system_integrity`, `balance_discrepancy`, etc.; consultados en `trading_tasks`, `trade.py`, `balance_validator`, `auto_circuit_breaker` | `app.state.breakers`, `/breakers/summary` expuesto; integrados en ciclo y rutas de órdenes |
| Validación filtros exchange (precio, lote, notional) | `order_validation.py`: usa `get_exchange_info()`, valida PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL; `binance_service`, `precision`, `auto_rebalancer_v2` usan exchange_info | Validación pre-orden en `trade.py` y servicios; exchange_info con cache |

> *"Usa modelos LSTM/Transformer y River para predecir régimen (tendencia, rango, alta volatilidad) y un StrategySelector que elige y parametriza la estrategia (grid, DCA, scalping, hedging) según esa predicción y el estado de la cuenta."*

| Componente | Ubicación | Producción |
|------------|-----------|------------|
| LSTM/Transformer + River | `hybrid_ml_engine.py`: modelos deep + River; `ml_engine.py`: River online | `ML_ENABLED=false` → **no** se cargan modelos en prod; motor en modo no operativo |
| StrategySelector | `strategy_selector.py`: `select_strategy(regime_prediction, account_state)`; estrategias por régimen (grid, DCA, etc.) | Usado en `trading_tasks`; con ML desactivado recibe `RegimePrediction` por defecto (RANGE) |
| Régimen (tendencia, rango, volatilidad) | `risk_manager.RegimePrediction`, `MarketRegime`; `strategy_selector` parametriza por régimen | Fallback estático cuando ML no está disponible |

---

## 3. Para quién / defensas

> *"Trading automatizado spot en Binance con riesgo controlado, observabilidad (Prometheus/Grafana, logs estructurados) y defensas (paradas de emergencia, reconciliación, idempotencia)."*

| Elemento | Código | Producción |
|----------|--------|------------|
| Prometheus | `PrometheusHTTPMiddleware`, `/metrics`, `app/core/metrics.py` (counters, gauges, histograms) | GET `/metrics` responde con métricas Prometheus |
| Grafana | Documentado; métricas expuestas para dashboards | Dashboards en `docker/grafana`; en Heroku se consumen las mismas métricas vía `/metrics` |
| Logs estructurados | JSON/logging en varios módulos; Papertrail como destino | Add-on Papertrail en app EU |
| Parada de emergencia | `risk_manager.emergency_stop`, `trigger_emergency_stop`; `risk_routes`: POST `/emergency-stop`; `strategy_selector` no opera si `emergency_stop` | `EMERGENCY_STOP=false`; endpoint disponible |
| Reconciliación | `ReconciliationService`, `run_reconciliation_cycle`; `main.py`: `recon.start(interval_seconds=60)`; scheduler: job cada 60s | Reconciliación cada **60 s** (≤60s cumplido) |
| Idempotencia | `operation_tracker.generate_client_order_id`, órdenes con `newClientOrderId` en `trade.py`; User Stream actualiza por `client_order_id` | OperationTracker y flujo de órdenes con client_order_id |

---

## 4. Integridad y prioridades

> *"Prioriza integridad y defensa (Decimal en cálculos, validaciones pre-orden, breakers, reconciliación ≤60s) y observabilidad end-to-end, con fallback seguro si falla el ML."*

| Requisito | Verificación |
|-----------|--------------|
| Decimal en cálculos | `Decimal` usado en `trade_executor`, `balance_service`, `commission`, `order_validation`, `fund_manager`, etc. |
| Validaciones pre-orden | `order_validation`, validación contra exchange_info (precio, lote, notional) y balance; bloqueo por breaker en `trade.py` |
| Breakers | Consultados antes de ejecutar ciclo y órdenes; activación automática por pérdidas/discrepancias (`auto_circuit_breaker`) |
| Reconciliación ≤60s | `interval_seconds=60` en `recon.start()` y en `run_reconciliation_forever` |
| Fallback seguro si falla ML | Con River/MLEngine no disponible se usa `RegimePrediction(long_regime=RANGE, short_regime=RANGE, ...)` y el ciclo sigue sin depender del ML |

---

## 5. Resumen

| Área | Estado |
|------|--------|
| Binance spot (paper/real) | ✅ Real en prod; paper vía `PAPER_TRADING` |
| Kelly fraccional | ✅ Implementado y usado en sizing |
| Circuit breakers | ✅ Activos, expuestos en `/breakers/summary`, integrados en ciclo y órdenes |
| Filtros exchange (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL) | ✅ Validación en order_validation y servicios |
| LSTM/Transformer + River | ⚠️ En código; en prod `ML_ENABLED=false` → solo fallback estático |
| StrategySelector | ✅ Usado; con ML off opera con régimen por defecto |
| Prometheus/Grafana | ✅ `/metrics` activo; dashboards documentados |
| Parada de emergencia | ✅ Endpoint y lógica; `EMERGENCY_STOP=false` en prod |
| Reconciliación ≤60s | ✅ Configurada a 60s |
| Idempotencia (client_order_id) | ✅ En flujo de órdenes y User Stream |
| Decimal y defensa | ✅ Decimal en rutas críticas; validaciones y breakers activos |
| Keep-alive / anti cold-start | ✅ `GET /ping` + loop keep-alive cada 10 min si `APP_URL` configurada |

**Conclusión (actualizado):** Tras la implementación de las Fases 1-5, la descripción de GridBot v2.5 coincide con el código y con lo desplegado en **grid-bot-ia-eu**. El ciclo de trading ahora usa la predicción de régimen de River (MLEngine) cuando `ML_ENABLED=true`, con fallback seguro a RANGE si el ML falla o está desactivado.

---

## 6. Verificación operativa continua

### Script automatizado

```bash
bash scripts/verify_production.sh
```

Comprueba: `/ping`, `/health`, `/metrics`, `/breakers/summary`, `/api/reconciliation/summary`, variables Heroku (`TRADING_ENABLED`, `EMERGENCY_STOP`, `PAPER_TRADING`, `ML_ENABLED`) y presencia de métricas ML.

**Frecuencia sugerida:** diaria o tras cada deploy.

### Checklist manual

| # | Verificación | Comando | Esperado |
|---|-------------|---------|----------|
| 1 | Proceso vivo | `curl $APP_URL/ping` | `{"pong": true}` |
| 2 | Salud | `curl $APP_URL/health` | `{"status": "ok", ...}` |
| 3 | Métricas Prometheus | `curl $APP_URL/metrics \| grep gridbot` | Líneas con métricas `gridbot_*` |
| 4 | Breakers | `curl $APP_URL/breakers/summary` | JSON con campo `breakers` |
| 5 | Reconciliación | `curl $APP_URL/api/reconciliation/summary` | `{"status": "ok", ...}` |
| 6 | TRADING_ENABLED | `heroku config:get TRADING_ENABLED -a grid-bot-ia-eu` | `true` |
| 7 | EMERGENCY_STOP | `heroku config:get EMERGENCY_STOP -a grid-bot-ia-eu` | `false` |
| 8 | PAPER_TRADING | `heroku config:get PAPER_TRADING -a grid-bot-ia-eu` | `false` |
| 9 | ML_ENABLED | `heroku config:get ML_ENABLED -a grid-bot-ia-eu` | `true` |
| 10 | ML usado en ciclo | `curl $APP_URL/metrics \| grep ml_regime_used` | Métrica presente con valor > 0 |

### Qué hacer si algo falla

- **Endpoint no responde:** Verificar dyno activo (`heroku ps -a grid-bot-ia-eu`). Si está idle, comprobar que `APP_URL` esté configurada para keep-alive.
- **Breakers activos:** `heroku logs --tail -a grid-bot-ia-eu` y buscar `breaker`. Evaluar si es legítimo; desactivar manualmente si procede.
- **ML metrics ausentes:** Verificar `ML_ENABLED=true`; si recién arrancó, el primer ciclo tarda hasta 5 min.
- **EMERGENCY_STOP=true:** Evaluar causa en logs; si es seguro, `heroku config:set EMERGENCY_STOP=false -a grid-bot-ia-eu`.

### Cold start y timeouts

La primera petición tras un período de inactividad puede tardar 10-30 segundos (cold start del dyno Heroku). El endpoint `GET /ping` es el más ligero y puede usarse para "calentar" el dyno antes de consultar endpoints pesados como `/metrics` o `/api/reconciliation/summary`. El loop de keep-alive (configurable vía `APP_URL`) reduce la probabilidad de cold start a prácticamente cero. La descripción de GridBot v2.5 coincide con el código y con lo desplegado en **grid-bot-ia-eu**. La única diferencia es que en producción el ML está desactivado (`ML_ENABLED=false`), por lo que el sistema usa el **fallback seguro** (régimen estático), tal como se indica en “fallback seguro si falla el ML”.
