## Mapa de Endpoints → Código

> **Actualizado**: 2025-01-XX
> **Nota**: Endpoints marcados con `(auth)` requieren autenticación mediante API key

### Endpoints de Sistema y Salud

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/` | GET | `app/main.py` | `root()` | No |
| `/health` | GET | `app/api/system_routes.py` | `health_check()` | No |
| `/health/liveness` | GET | `app/api/system_routes.py` | `liveness()` | No |
| `/health/readiness` | GET | `app/api/system_routes.py` | `readiness()` | No |

### Endpoints de Trading

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/order` | POST | `app/api/trade.py` | `place_order()` | Sí |
| `/api/trade/order` | POST | `app/api/trade.py` | `place_order()` | Sí |

_Notas trading:_ `type=MARKET` puede ejecutarse vía `BrokerAdapter` si `USE_BROKER_ADAPTER=true` y `BROKER_PRIMARY_VENUE=binance_spot` (mismo criterio que `TradeExecutor`); fallback a `python-binance` ante desfase `-1021`. `LIMIT` sigue por cliente directo. Métrica: `gridbot_spot_market_submit_path_total` (`source=http_trade`).

_Notas trading:_ `type=MARKET` puede ejecutarse vía `BrokerAdapter` si `USE_BROKER_ADAPTER=true` y `BROKER_PRIMARY_VENUE=binance_spot` (mismo criterio que `TradeExecutor`); fallback a `python-binance` ante desfase `-1021`. `LIMIT` sigue por cliente directo. Métrica: `gridbot_spot_market_submit_path_total` (`source=http_trade`).
| `/api/trades` | GET | `app/api/trade.py` | `get_trades()` | Sí |
| `/api/trade/trades` | GET | `app/api/trade.py` | `get_trades()` | Sí |
| `/balances` | GET | `app/api/trade.py` | `get_balances()` | No |
| `/api/trade/balances` | GET | `app/api/trade.py` | `get_balances()` | No |
| `/price/{symbol}` | GET | `app/api/trade.py` | `get_price()` | No |
| `/api/trade/price/{symbol}` | GET | `app/api/trade.py` | `get_price()` | No |
| `/binance_status` | GET | `app/api/trade.py` | `binance_status()` | No |
| `/run_grid` | POST | `app/api/trade.py` | `run_grid()` | Sí |
| `/api/trade/run_grid` | POST | `app/api/trade.py` | `run_grid()` | Sí |
| `/grid_config` | GET | `app/api/trade.py` | `get_grid_config_endpoint()` | Sí |
| `/grid_config` | POST | `app/api/trade.py` | `update_grid_config()` | Sí |

### Endpoints de Portfolio

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/api/portfolio/summary` | GET | `app/api/portfolio_routes.py` | `get_portfolio_summary()` | No |
| `/api/portfolio/positions` | GET | `app/api/portfolio_routes.py` | `get_portfolio_positions()` | No |
| `/api/positions` | GET | `app/main.py` | `get_positions()` | No |

### Endpoints de Seguridad e Integridad

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/breakers/summary` | GET | `app/api/breakers_routes.py` | `breakers_summary()` | No |
| `/breakers/status` | GET | `app/api/breakers_routes.py` | `breakers_status()` | No |
| `/api/breakers/summary` | GET | `app/api/breakers_routes.py` | `breakers_summary_api()` | No |
| `/api/breakers/status` | GET | `app/api/breakers_routes.py` | `breakers_status_api()` | No |
| `/api/reconciliation/summary` | GET | `app/api/reconciliation_routes.py` | `reconciliation_summary()` | No |
| `/integrity/status` | GET | `app/main.py` | `get_integrity_status()` | No |
| `/integrity/validate-balances` | POST | `app/main.py` | `force_balance_validation()` | No |
| `/integrity/check-operations` | POST | `app/main.py` | `force_operation_check()` | No |
| `/integrity/operations/failed` | GET | `app/main.py` | `get_failed_operations()` | No |
| `/integrity/operations/partial-fills` | GET | `app/main.py` | `get_partial_fills()` | No |
| `/integrity/balances/discrepancies` | GET | `app/main.py` | `get_balance_discrepancies()` | No |
| `/integrity/update-binance-balance` | POST | `app/main.py` | `update_binance_balance()` | No |
| `/integrity/auto-correct-balance` | POST | `app/main.py` | `auto_correct_balance()` | No |

### Endpoints de Métricas y Observabilidad

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/metrics` | GET | `app/api/prometheus.py` | `metrics()` | No |
| `/api/metrics/` | GET | `app/api/metrics.py` | `metrics()` | No |
| `/api/metrics/update-pnl` | POST | `app/api/metrics.py` | `update_pnl_metrics()` | Sí |
| `/api/metrics/prometheus` | GET | `app/api/metrics_routes.py` | `get_prometheus_metrics()` | No |

### Endpoints de Estrategias

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/api/strategies` | GET | `app/main.py` | `list_strategies()` | Sí |
| `/api/v2/strategies/execute_intelligent` | POST | `app/api/strategy_routes.py` | `execute_intelligent_strategy()` | Sí |
| `/api/v2/strategies/last_decision` | GET | `app/api/strategy_routes.py` | `get_last_decision()` | No |
| `/api/v2/strategies/backtest/run` | POST | `app/api/strategy_routes.py` | `run_backtest()` | Sí |
| `/api/v2/strategies/ml/status` | GET | `app/api/strategy_routes.py` | `ml_status()` | No |
| `/strategy/trailing_stop` | POST | `app/api/strategies.py` | `run_trailing_stop()` | Sí |
| `/strategy/scalping` | POST | `app/api/strategies.py` | `run_scalping()` | Sí |
| `/strategy/rsi_macd` | POST | `app/api/strategies.py` | `run_rsi_macd()` | Sí |
| `/strategy/backtest` | POST | `app/api/strategies.py` | `backtest_strategy()` | Sí |

_Nota:_ el body de `POST /api/v2/strategies/backtest/run` puede incluir `persist_run_to_db: true` para guardar la corrida en `backtest_runs` / `backtest_metrics` (requiere migración `20260503_backtest_runs`).

### Endpoints de Riesgo

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/api/v2/risk/status` | GET | `app/api/risk_routes.py` | `get_risk_status()` | No |
| `/api/v2/risk/emergency-stop` | POST | `app/api/risk_routes.py` | `emergency_stop()` | Sí |
| `/api/v2/risk/calculate-position-size` | POST | `app/api/risk_routes.py` | `calculate_position_size()` | No |
| `/api/v2/risk/calculate-trailing-stop` | POST | `app/api/risk_routes.py` | `calculate_trailing_stop()` | No |

### Endpoints de Comisiones (v1)

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/api/v1/commissions/rates` | GET | `app/api/commission_routes.py` | `get_commission_rates()` | Sí |
| `/api/v1/commissions/calculate` | POST | `app/api/commission_routes.py` | `calculate_commission()` | Sí |
| `/api/v1/commissions/validate-profitability` | POST | `app/api/commission_routes.py` | `validate_grid_profitability()` | Sí |
| `/api/v1/commissions/calculate-profit` | POST | `app/api/commission_routes.py` | `calculate_profit_with_commissions()` | Sí |
| `/api/v1/commissions/update-rates` | GET | `app/api/commission_routes.py` | `update_commission_rates()` | Sí |
| `/api/v1/commissions/status` | GET | `app/api/commission_routes.py` | `get_commission_status()` | Sí |
| `/api/v1/commissions/transaction-cost-audit` | POST | `app/api/commission_routes.py` | `post_transaction_cost_audit()` | Sí |

### Endpoints de Configuración

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/api/config/` | GET | `app/api/config_routes.py` | `config_home()` | No |
| `/api/config/summary` | GET | `app/api/config_routes.py` | `get_config_summary()` | No |
| `/api/config/assets` | GET | `app/api/config_routes.py` | `get_assets()` | No |
| `/api/config/assets/{symbol}` | GET | `app/api/config_routes.py` | `get_asset()` | No |
| `/api/config/assets/{symbol}` | PUT | `app/api/config_routes.py` | `update_asset()` | Sí |
| `/api/config/assets` | POST | `app/api/config_routes.py` | `create_asset()` | Sí |
| `/api/config/assets/{symbol}` | DELETE | `app/api/config_routes.py` | `delete_asset()` | Sí |

### Endpoints de Simulación

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/api/simulations/dry-run` | POST | `app/api/simulations.py` | `dry_run()` | Sí |
| `/api/simulations/transaction-cost-audit` | POST | `app/api/simulations.py` | `transaction_cost_audit()` | Sí |

### Endpoints de Alertas

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/alerts/critical` | POST | `app/api/alert_routes.py` | `send_critical_alert()` | No |
| `/alerts/warning` | POST | `app/api/alert_routes.py` | `send_warning_alert()` | No |

### Endpoints de Optimización

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/api/optimized/health` | GET | `app/api/optimized_routes.py` | `health()` | No |
| `/api/optimized/status` | GET | `app/api/optimized_routes.py` | `status()` | No |
| `/api/optimized/trading/cycle` | POST | `app/api/optimized_routes.py` | `run_trading_cycle()` | Sí |

### Endpoints de Binance Sync

| Endpoint | Método | Archivo | Función | Auth |
|---|---|---|---|---|
| `/api/v1/binance/sync/account` | POST | `app/api/binance_sync_routes.py` | `sync_binance_account()` | No |
| `/api/v1/binance/sync/balances` | POST | `app/api/binance_sync_routes.py` | `sync_binance_balances()` | No |

---

## Notas

- **Autenticación**: Los endpoints marcados con `(auth)` requieren header `Authorization: Bearer <API_KEY>`
- **Prefijos**: Algunos endpoints están disponibles en múltiples rutas por compatibilidad (ej: `/order` y `/api/trade/order`)
- **Documentación completa**: Para contratos completos con schemas, ver `docs/openapi.json` o `/docs` en la API en ejecución
