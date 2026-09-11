## Catálogo de Métricas Prometheus

> **Actualizado**: 2025-01-XX
> **Origen**: `app/core/metrics.py` y middleware

### MÉTRICAS DE RENTABILIDAD

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `profit_total_usdt` | Gauge | `strategy` | Ganancia total acumulada en USDT |
| `profit_daily_usdt` | Gauge | `strategy` | Ganancia diaria en USDT |
| `profit_by_asset_usdt` | Gauge | `asset`, `strategy` | Ganancia por activo en USDT |
| `roi_daily_percent` | Gauge | `strategy` | ROI diario en porcentaje |
| `roi_total_percent` | Gauge | `strategy` | ROI total en porcentaje |
| `roi_by_asset_percent` | Gauge | `asset`, `strategy` | ROI por activo en porcentaje |
| `gridbot_profit_loss` | Gauge | – | PnL agregado de GridBot en USDT |

### MÉTRICAS DE PORTAFOLIO

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `portfolio_total_value_usdt` | Gauge | `strategy` | Valor total del portafolio en USDT |
| `portfolio_change_usdt` | Gauge | `strategy` | Cambio del portafolio vs baseline en USDT |
| `cash_balance_usdt` | Gauge | `strategy` | Saldo efectivo en USDT (caja) |
| `balance_by_asset` | Gauge | `asset`, `strategy` | Saldo por activo |
| `active_positions_count` | Gauge | `strategy` | Número de posiciones activas |

### MÉTRICAS DE SEGURIDAD Y CIRCUIT BREAKERS

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `active_breakers_total` | Gauge | – | Cantidad de circuit breakers activos |
| `breaker_state` | Gauge | `type` | Estado de breaker (0 inactivo, 1 activo) por tipo |
| `order_validation_rejects_total` | Counter | `reason`, `symbol` | Total de rechazos de validación de órdenes |
| `integrity_score` | Gauge | `component` | Score de integridad (0-100) por componente |
| `ic1_stop_rebuy_active` | Gauge | – | 1 si IC-1 freno fuera de rango activo (E7) |
| `ic2_flatten_active` | Gauge | – | 1 si IC-2 flatten Core activo / desarmado (E7) |
| `ic1_trips_total` | Counter | – | Activaciones IC-1 |
| `ic2_trips_total` | Counter | – | Activaciones IC-2 |

### MÉTRICAS DE OPERACIONES Y TRADING

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `trades_executed_total` | Counter | `side`, `asset`, `strategy` | Total de trades ejecutados |
| `trades_successful_total` | Counter | `asset`, `strategy` | Total de trades exitosos |
| `trades_failed_total` | Counter | `asset`, `strategy` | Total de trades fallidos |
| `trades_success_rate` | Gauge | `strategy` | Tasa de éxito de trades (0-1) |
| `gridbot_transaction_cost_audit_requests_total` | Counter | `order_type` | Llamadas a `/api/simulations/transaction-cost-audit` |
| `gridbot_backtest_run_persist_total` | Counter | `outcome` | Persistencia de corridas de backtest (`success` / `failure`) |
| `gridbot_monte_carlo_run_persist_total` | Counter | `outcome` | Persistencia de estudios MC drawdown del promotion gate (`success` / `failure`) |
| `gridbot_monte_carlo_retention_prune_total` | Counter | `outcome` | Poda de retención `monte_carlo_runs` (`success` / `failure`) |
| `gridbot_monte_carlo_retention_rows_deleted_total` | Counter | – | Filas eliminadas por retención MC: `KEEP_LAST` y/o `MAX_AGE_DAYS` (acumulado) |
| `gridbot_orders_total` | Counter | `side`, `asset`, `strategy` | Total de órdenes procesadas por GridBot |
| `gridbot_trade_executor_order_path_total` | Counter | `path` | TradeExecutor: `broker_adapter` vs `legacy` (singleton python-binance) |
| `gridbot_spot_market_submit_path_total` | Counter | `source`, `path` | MARKET spot: `source` = `http_trade` \| `grid_manager`; `path` = `broker_adapter` \| `binance_client` |
| `gridbot_volume_total` | Counter | `asset`, `strategy` | Volumen total de trading en USDT |
| `trade_execution_duration_seconds` | Histogram | `asset`, `strategy` | Duración de ejecución de trades |
| `partial_fills_total` | Counter | – | Total de órdenes parcialmente llenadas |

### MÉTRICAS DE CICLOS DE TRADING

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `cycle_phase_timestamp` | Gauge | `phase` | Timestamp de la fase actual del ciclo (evaluation/execution) |
| `cycle_decision_ready` | Gauge | `symbol`, `strategy` | Decisión de ciclo lista (minuto 4) |
| `cycle_order_executed` | Gauge | `symbol`, `status` | Orden ejecutada en el ciclo (minuto 5) |
| `grid_cycle_duration_seconds` | Histogram | – | Duración del ciclo grid en segundos |
| `gridbot_ml_regime_used_in_cycle_total` | Counter | `symbol` | Ciclos que aplicaron régimen ML híbrido |
| `gridbot_ml_regime_fallback_total` | Counter | `symbol`, `reason` | Fallback a régimen estático (`disabled`, `error`, `promotion_gate`, …) |
| `gridbot_ml_promotion_gate_blocks_total` | Counter | `symbol`, `reason` | Bloqueos del gate (TQS + Monte Carlo + backtest after-cost + sentimiento opcional vía Redis). Razones típicas: `tqs_direction_flat`, `tqs_combined_too_weak`, `monte_carlo_required_missing`, `monte_carlo_p95_exceeds_cap`, `after_cost_backtest_required_missing`, `after_cost_sharpe_below_min`, `after_cost_sharpe_unavailable`, `after_cost_drawdown_unavailable`, `after_cost_drawdown_exceeds_cap`, `after_cost_total_return_unavailable`, `after_cost_total_return_below_min`, `after_cost_backtest_dd_too_small_for_mc_alignment`, `mc_p95_exceeds_backtest_dd_ratio`, `nlp_sentiment_below_min`, `nlp_sentiment_unavailable`. |
| `gridbot_kelly_sentiment_scale_total` | Counter | `symbol`, `band` | Con `KELLY_SENTIMENT_SCALE_ENABLED=true`, una muestra por símbolo y ciclo en fase evaluación: `no_score`, `scaled_down`, `unchanged`, `scaled_up` (según multiplicador vs 1.0). |

### MÉTRICAS DE API Y REQUESTS

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `gridbot_api_requests_total` | Counter | `method`, `endpoint`, `status_code` | Total de requests de API |
| `api_request_duration_seconds` | Histogram | `method`, `endpoint` | Duración de requests de API |
| `order_api_failures_total` | Counter | `reason` | Fallos de API al enviar/consultar órdenes |
| `http_requests_total` | Counter | `method`, `path`, `status` | Total de requests HTTP (middleware) |
| `http_request_duration_seconds` | Histogram | `method`, `path`, `status` | Latencia de requests HTTP (middleware) |

### MÉTRICAS DE RECONCILIACIÓN E INTEGRIDAD

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `reconciliation_latency_seconds` | Histogram | – | Tiempo de ejecución del ciclo de reconciliación |
| `reconciliation_discrepancies_total` | Counter | `type` | Total de discrepancias de reconciliación detectadas |
| `reconciliation_accuracy_percent` | Gauge | – | Precisión de reconciliación en porcentaje (0-100) |
| `balance_discrepancy_usd` | Gauge | – | Discrepancia absoluta de balance entre sistema y Binance en USD |
| `unaccounted_pnl_usd` | Gauge | – | PnL no contabilizado detectado en reconciliación en USD |

### MÉTRICAS DE ESTADO DEL BOT

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `bot_status` | Gauge | `strategy` | Estado del bot (1=activo, 0=inactivo) |
| `bot_last_execution_timestamp` | Gauge | `strategy` | Timestamp de la última ejecución del bot |
| `bot_errors_total` | Counter | `error_type`, `strategy` | Total de errores del bot |

### MÉTRICAS DE BINANCE Y SERVICIOS EXTERNOS

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `binance_api_errors_total` | Counter | `code`, `phase` | Total de errores de API de Binance |
| `binance_ip_rejected` | Gauge | — | 1 si el último validate/get_account falló por IP no autorizada (−2015) **o** el flag compartido `gridbot:binance_auth_ip_blocked=1` (worker). Distingue API `up` de Binance autenticado bloqueado. No usar `increase()`. No bajar a 0 por fallback ccxt tras −2015. |
| `gridbot_si_ops_state_inconsistent` | Gauge | — | 1 si SI está active con `operational_state` leftover CLOSED. Solo diagnóstico de copy; **no** muta el breaker. |
| `external_auth_failures_total` | Counter | `provider`, `reason` | Total de fallos de autenticación/permiso con proveedores externos |
| `commission_update_failures_total` | Counter | `provider`, `reason` | Total de fallos al actualizar comisiones externas |

### MÉTRICAS DE CONCURRENCIA (Bug Fixes)

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `balance_update_conflicts_total` | Counter | `asset` | Total de conflictos detectados en updates de balance (optimistic locking) |
| `distributed_lock_acquired_total` | Counter | `lock_name` | Total de locks distribuidos adquiridos exitosamente |
| `distributed_lock_skipped_total` | Counter | `lock_name`, `function` | Total de ejecuciones omitidas por lock tomado |
| `distributed_lock_errors_total` | Counter | `lock_name`, `error_type` | Total de errores en locks distribuidos |
| `distributed_lock_duration_seconds` | Histogram | `lock_name` | Duración de locks distribuidos en segundos |

### MÉTRICAS DE WEBSOCKET (User Data Stream)

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `ws_events_total` | Counter | `event` | Total de eventos recibidos por WebSocket user stream |
| `ws_reconnects_total` | Counter | – | Total de reconexiones realizadas en WebSocket user stream |
| `ws_errors_total` | Counter | `phase` | Total de errores en WebSocket user stream |
| `ws_fill_latency_seconds` | Histogram | – | Latencia de procesamiento de fills recibidos por WebSocket |

### MÉTRICAS DE POLVO (DUST)

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `dust_assets_count` | Gauge | – | Cantidad de activos con valor < 1 USDT |
| `dust_value_usd` | Gauge | – | Suma de valor (USDT) de activos < 1 USDT |
| `dust_swept_usd_total` | Counter | – | Valor total (USDT) barrido (vendido/convertido) como polvo |
| `last_dust_sweep_timestamp` | Gauge | – | Timestamp unix del último barrido de polvo |

### MÉTRICAS DE SÍMBOLOS

| Métrica | Tipo | Labels | Descripción |
|---|---|---|---|
| `invalid_symbol_total` | Counter | `symbol` | Total de ocurrencias de símbolo inválido normalizado |

---

## Consultas PromQL Útiles

### Rentabilidad
```promql
# Ganancia total por estrategia
sum by (strategy) (profit_total_usdt)

# ROI diario promedio
avg(roi_daily_percent)

# Portfolio total
sum by (strategy) (portfolio_total_value_usdt)
```

### Seguridad
```promql
# Circuit breakers activos
active_breakers_total

# Estado de breakers por tipo
sum by (type) (breaker_state)

# Rechazos de validación
sum by (reason) (rate(order_validation_rejects_total[5m]))
```

### Trading
```promql
# Tasa de trades ejecutados
rate(trades_executed_total[5m])

# Tasa de éxito
avg(trades_success_rate)

# Volumen de trading
sum by (asset) (rate(gridbot_volume_total[5m]))
```

### Integridad
```promql
# Latencia de reconciliación
histogram_quantile(0.99, rate(reconciliation_latency_seconds_bucket[5m]))

# Discrepancias de balance
balance_discrepancy_usd

# Score de integridad
avg(integrity_score)
```

### Performance
```promql
# Latencia P99 de requests HTTP
histogram_quantile(0.99, sum by (le, path) (rate(http_request_duration_seconds_bucket[5m])))

# Requests por segundo
sum by (path) (rate(http_requests_total[5m]))

# Latencia de ejecución de trades
histogram_quantile(0.95, rate(trade_execution_duration_seconds_bucket[5m]))
```

### Errores
```promql
# Errores del bot por tipo
sum by (error_type) (rate(bot_errors_total[5m]))

# Errores de Binance API
sum by (code) (rate(binance_api_errors_total[5m]))

# Errores de WebSocket
sum by (phase) (rate(ws_errors_total[5m]))
```
