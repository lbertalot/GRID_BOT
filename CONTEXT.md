# CONTEXT.md — Descripción Real del Sistema GridBot v2.5

> Última sincronización con código: 2026-02-17
> Fuente de verdad: código en `/workspace/app/`

---

## 1. Visión General

GridBot v2.5 es un sistema de trading algorítmico automatizado para **Binance Spot**.
Combina grid trading con machine learning para adaptar la estrategia al régimen de mercado.

- **Exchange**: Binance (spot únicamente, no futuros)
- **Modos**: Paper trading y trading real
- **Ejecución**: Continua en producción (API + workers Celery)

---

## 2. Stack Tecnológico Real (verificado en requirements.txt y código)

| Componente | Tecnología | Versión |
|---|---|---|
| API | FastAPI | 0.104.1 |
| Server | Uvicorn | 0.24.0 |
| ORM | SQLAlchemy | 2.0.23 |
| BD | PostgreSQL | via psycopg2-binary 2.9.9 |
| Migraciones | Alembic | 1.12.1 |
| Broker/Cache | Redis | 5.0.1 |
| Workers | Celery | 5.3.4 |
| Métricas | prometheus-client | 0.19.0 |
| Dashboards | Grafana | (vía Docker) |
| Exchange SDK | python-binance | 1.0.19 |
| WebSocket | unicorn-binance-websocket-api | 1.45.0 |
| ML online | River | (opcional, requirements-ml.txt) |
| ML deep | TensorFlow/Keras | (opcional, requirements-ml.txt) |
| Validación | Pydantic v2 | 2.5.0 |
| Testing | pytest + httpx | 7.4.3 / 0.25.2 |
| Alertas | python-telegram-bot | 20.7 |
| Python | >= 3.11 | (runtime.txt) |

---

## 3. Módulos Existentes

### 3.1 API (`app/api/`)

| Archivo | Propósito |
|---|---|
| `trade.py` | Endpoints de trading: orden, grid, balances |
| `strategies.py` | Gestión de estrategias |
| `metrics.py` | Endpoints de métricas de trading |
| `metrics_routes.py` | Rutas adicionales de métricas |
| `prometheus.py` | Endpoint `/metrics` para Prometheus |
| `alert_routes.py` | Gestión de alertas |
| `config_routes.py` | Configuración del sistema |
| `system_routes.py` | Rutas de sistema |
| `integrity_routes.py` | Endpoints de integridad |
| `reconciliation_routes.py` | Endpoints de reconciliación |
| `breakers_routes.py` | Gestión de circuit breakers |
| `portfolio_routes.py` | Posiciones y portafolio |
| `risk_routes.py` | Endpoints de riesgo |
| `strategy_routes.py` | Rutas de selección de estrategia |
| `simulations.py` | Simulaciones y backtesting |
| `commission_routes.py` | Comisiones |
| `binance_sync_routes.py` | Sincronización con Binance |
| `optimized_routes.py` | Rutas optimizadas |
| `test_routes.py` | Rutas de prueba |

### 3.2 Core (`app/core/`)

| Archivo | Propósito |
|---|---|
| `config.py` | Settings (Pydantic BaseSettings): DB, Redis, API keys |
| `circuit_breakers.py` | CircuitBreakers: 4 tipos (balance_discrepancy, operation_failure_rate, system_integrity, critical_mode) |
| `auto_circuit_breaker.py` | Circuit breaker automático |
| `metrics.py` | Todas las métricas Prometheus + TradingMetrics class |
| `risk_manager.py` | RiskManager: Kelly fraccional, trailing stops, régimen de mercado |
| `auth.py` | Autenticación Bearer token |
| `celery_app.py` | Configuración Celery + beat schedule |
| `distributed_lock.py` | Lock distribuido Redis para Celery tasks |
| `balance_validator.py` | Validación cruzada de balances |
| `operation_tracker.py` | Tracking de operaciones |
| `integrity_monitor.py` | Monitor de integridad del sistema |
| `paper_trading.py` | PaperTradingSystem |
| `precision.py` | Utilidades de precisión numérica |
| `precision_validator.py` | Validador de precisión |
| `safety_validator.py` | Validador de seguridad |
| `balance_optimizer.py` | Optimizador de balances |
| `strategy_blacklist.py` | Blacklist de estrategias |
| `trading_errors.py` | Errores específicos de trading |
| `error_handler.py` | Manejador centralizado de errores |
| `error_handlers.py` | Handlers adicionales |
| `structured_logger.py` | Logger JSON estructurado |
| `logging_config.py` | Configuración de logging |
| `trading_logger.py` | Logger específico de trading |
| `database.py` | Configuración de base de datos |
| `sqlalchemy_config.py` | Config de SQLAlchemy |
| `redis_cache.py` | Cache Redis |
| `telegram_bot.py` | Bot de Telegram |
| `binance_proxy.py` | Proxy para Binance |
| `commission_aware_trading.py` | Trading con awareness de comisiones |
| `trade_auditor.py` | Auditor de trades |
| `unified_config.py` | Configuración unificada |
| `paths.py` | Paths del proyecto |
| `monitoring.py` | Monitoreo general |
| `continuous_monitoring.py` | Monitoreo continuo |
| `grafana_metrics.py` | Métricas para Grafana |
| `metrics_manager.py` | Manager de métricas |
| `performance_utils.py` | Utilidades de rendimiento |
| `optimized_grid_manager.py` | Grid manager optimizado |
| `optimized_logging.py` | Logging optimizado |

#### Middleware (`app/core/middleware/`)

| Archivo | Propósito |
|---|---|
| `prometheus_http.py` | PrometheusHTTPMiddleware: métricas HTTP por ruta |
| `integrity_guard.py` | IntegrityGuardMiddleware: bloquea escrituras cuando breakers activos |

### 3.3 Servicios (`app/services/`)

| Archivo | Propósito |
|---|---|
| `order_validation.py` | OrderValidator: valida PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL |
| `trade_executor.py` | TradeExecutor: ejecuta órdenes con sync de balances |
| `trading_tasks.py` | Celery tasks de trading: ciclo 5m, dust sweep, risk assessment |
| `reconciliation_service.py` | ReconciliationService: reconciliación ≤ 60s con Binance |
| `strategy_selector.py` | StrategySelector: selecciona estrategia por régimen |
| `ml_engine.py` | MLEngine: River online (LogisticRegression + ADWIN) |
| `hybrid_ml_engine.py` | HybridMLEngine: LSTM/Transformer + River |
| `risk_manager.py` | Servicio de gestión de riesgo |
| `binance_client.py` | Cliente Binance directo |
| `binance_client_singleton.py` | Singleton del cliente Binance |
| `binance_async.py` | AsyncBinanceWrapper |
| `binance_service.py` | Servicio general de Binance |
| `binance_data_sync.py` | Sincronización de datos con Binance |
| `binance_user_stream.py` | WebSocket User Data Stream |
| `binance_trades_pnl.py` | PnL basado en trades de Binance |
| `binance_credentials.py` | Gestión de credenciales |
| `balance_service.py` | Servicio de balances |
| `balance_updater.py` | Actualizador de balances |
| `fund_manager.py` | Gestor de fondos |
| `pnl_service.py` | Servicio de PnL |
| `metrics_service.py` | Servicio de métricas |
| `metrics_updater.py` | Actualizador de métricas |
| `grid_strategy.py` | Estrategia grid |
| `strategy_manager.py` | Gestor de estrategias |
| `strategy_factory.py` | Factory de estrategias |
| `config_manager.py` | Gestor de configuración |
| `commission_manager.py` | Gestor de comisiones |
| `commission.py` | Cálculo de comisiones |
| `telegram_alert.py` | Alertas por Telegram |
| `alert_tasks.py` | Tasks de alertas |
| `market_data_collector.py` | Recolector de datos de mercado |
| `performance_analyzer.py` | Analizador de rendimiento |
| `cache.py` | Servicio de cache |
| `auto_rebalancer.py` | Auto-rebalanceador v1 |
| `auto_rebalancer_v2.py` | Auto-rebalanceador v2 |
| `rebalancing_tasks.py` | Tasks de rebalanceo |
| `ml_tasks.py` | Tasks de ML |
| `backtesting_service.py` | Servicio de backtesting |
| `symbol_validator.py` | Validador de símbolos |
| `symbol_error_filter.py` | Filtro de errores por símbolo |
| `min_qty_updater.py` | Actualizador de cantidades mínimas |
| `asset_limit_updater.py` | Actualizador de límites por activo |
| `user_stream_handler.py` | Handler del user stream |
| `order_validation_dependency.py` | Dependencia de validación de órdenes |

#### Sub-estrategias (`app/services/strategies/`)

| Archivo | Propósito |
|---|---|
| `base.py` | Clase base de estrategia |
| `rsi_macd.py` | Estrategia RSI + MACD |
| `trailing_stop.py` | Trailing stop |
| `scalping.py` | Estrategia de scalping |

### 3.4 Estrategias Top-Level (`app/strategies/`)

| Archivo | Propósito |
|---|---|
| `base.py` | Base de estrategias |
| `scalping_strategy.py` | Scalping strategy |
| `dca_strategy.py` | DCA strategy |

### 3.5 Modelos (`app/models/`)

| Archivo | Propósito |
|---|---|
| `trade.py` | Trade: id, symbol, side, quantity, entry_price, exit_price, profit_loss, timestamp |
| `balance.py` | Modelo de balances |
| `grid_config.py` | Configuración de grid |
| `alerts.py` | Alertas |
| `system_config.py` | Configuración del sistema |
| `system_setting.py` | Settings del sistema |
| `performance_metrics.py` | Métricas de rendimiento |
| `asset_limit.py` | Límites por activo |
| `portfolio_schemas.py` | Schemas de portafolio |

### 3.6 Schemas (`app/schemas/`)

| Archivo | Propósito |
|---|---|
| `validation.py` | OrderRequest, GridParams, StrategyParams (Pydantic v2) |
| `simple_validation.py` | Validaciones simplificadas |
| `improved_validation.py` | Validaciones mejoradas |

### 3.7 Scheduler (`app/scheduler/`)

| Archivo | Propósito |
|---|---|
| `grid_job.py` | Job de grid |
| `reconciliation_job.py` | Job de reconciliación |
| `optimized_scheduler.py` | Scheduler optimizado |
| `operation_tracking_job.py` | Job de tracking de operaciones |

### 3.8 Exchanges (`app/exchanges/`)

| Archivo | Propósito |
|---|---|
| `binance_client.py` | Cliente de exchange |
| `exceptions.py` | Excepciones del exchange (SymbolFilterError) |

---

## 4. Celery Beat Schedule (verificado en `app/core/celery_app.py`)

| Tarea | Intervalo | Cola |
|---|---|---|
| `trading_cycle_tick` | 60s | default |
| `check_and_rebalance` | 3600s (1h) | default |
| `analyze_performance` | Diario 00:00 UTC | default |
| `assess_risk` | 300s (5m) | default |
| `dust_sweep` | Domingos 03:00 UTC | low (dry_run=True) |

---

## 5. Circuit Breakers (verificado en `app/core/circuit_breakers.py`)

| Breaker | Propósito |
|---|---|
| `balance_discrepancy` | Discrepancia entre balance interno y Binance |
| `operation_failure_rate` | Tasa alta de fallos en operaciones |
| `system_integrity` | Problemas de integridad del sistema |
| `critical_mode` | Modo de emergencia: activa todos los breakers |

Comportamiento: Cualquier breaker activo → `is_trading_halted() == True` → IntegrityGuardMiddleware bloquea POST/PUT/DELETE en rutas protegidas.

Cooldown configurable vía `CB_COOLDOWN_SECONDS` (default: 300s).

---

## 6. Regímenes de Mercado (verificado en `app/core/risk_manager.py`)

| Régimen | Multiplicador de Exposición |
|---|---|
| `BULL_TREND` | 1.0 |
| `RANGE` | 1.0 |
| `HIGH_VOL` | 0.8 |
| `BEAR_TREND` | 0.7 |
| `HIGH_VOLATILITY_BEAR` | 0.5 |
| `CRASH_IMMINENT` | 0.5 |

---

## 7. Estrategias Disponibles (verificado en `app/services/strategy_selector.py`)

| StrategyType | Condición de Selección |
|---|---|
| `GridTrading` | RANGE + LOW_VOL |
| `DCA` | BULL_TREND + MODERATE_VOL |
| `Scalping` | BULL_TREND + HIGH_VOL |
| `HOLD` | BEAR_TREND / CRASH_IMMINENT |
| `Hedging` | HIGH_VOLATILITY_BEAR |

Fallback: Si error en selección → HOLD (confianza 0.5).

---

## 8. ML Engines

### 8.1 MLEngine (`app/services/ml_engine.py`)
- Modelo: River LogisticRegression online + StandardScaler
- Detector de drift: ADWIN
- Features: volatility, spread, volume, RSI, ATR
- Fallback si River no disponible: `RegimePrediction(label=0, proba=0.5)`

### 8.2 HybridMLEngine (`app/services/hybrid_ml_engine.py`)
- Deep learning: LSTM y Transformer (TensorFlow/Keras)
- Online: River (HoeffdingTree, AdaptiveRandomForest, LogisticRegression)
- Combina predicción largo plazo (deep) + corto plazo (River)
- Fallback: `RegimePrediction(long=RANGE, short=RANGE, conf=0.5)`

---

## 9. Restricciones Reales

- **PRICE_FILTER**: tickSize obligatorio para órdenes LIMIT.
- **LOT_SIZE**: stepSize, minQty, maxQty obligatorios.
- **MIN_NOTIONAL**: cantidad × precio >= minNotional del exchange.
- **Balance check**: verificación de saldo antes de cada orden.
- **Decimal**: usado en `order_validation.py`, `trade_executor.py`, `paper_trading.py`.
- **Reconciliación**: cada 60s, compara estado interno vs Binance.
- **Idempotencia**: `client_order_id` para operaciones con el exchange.
- **Auth**: Bearer token requerido en endpoints protegidos.
- **Paper trading**: controlado por `PAPER_TRADING` env var.
- **Emergency stop**: `EMERGENCY_STOP` env var + `RiskManager.trigger_emergency_stop()`.

---

## 10. Observabilidad

- **Prometheus endpoint**: `GET /metrics`
- **Métricas clave**: ver `app/core/metrics.py` (60+ métricas registradas)
- **Dashboards Grafana**: `docker/grafana/dashboards/`
- **Logs**: JSON estructurado configurable
- **Alertas**: Telegram vía `python-telegram-bot`
- **Alert rules**: `gridbot.rules.yml`

---

## 11. Despliegue

- Docker Compose con profiles (development, production)
- Heroku compatible (Procfile, runtime.txt)
- Nginx reverse proxy (docker/nginx/)
- SSL configurable (docker/ssl/)
