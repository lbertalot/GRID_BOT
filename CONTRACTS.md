# CONTRACTS.md — Contratos Formales entre Módulos de GridBot v2.5

> Última sincronización con código: 2026-02-17
> Fuente de verdad: código fuente. Si este documento diverge del código, el código prevalece.

---

## 1. Convenciones de Este Documento

- **Input**: parámetros que el módulo recibe.
- **Output**: valor de retorno o efecto secundario.
- **Errores**: excepciones o estados de error posibles.
- **Responsabilidad**: qué garantiza este módulo y qué NO garantiza.
- `UNDEFINED BEHAVIOR`: el código no define claramente el comportamiento en ese caso.

---

## 2. CircuitBreakers (`app/core/circuit_breakers.py`)

### `CircuitBreakers.__init__()`
- **Output**: Instancia con 4 breakers inicializados en `active=False`.
- **Efecto**: Lee `CB_COOLDOWN_SECONDS` del entorno (default 300).

### `async activate_breaker(breaker_type: str, reason: str = None) -> bool`
- **Input**: `breaker_type` ∈ {`balance_discrepancy`, `operation_failure_rate`, `system_integrity`, `critical_mode`}, `reason` string.
- **Output**: `True` si se activó exitosamente, `False` si tipo desconocido o en cooldown.
- **Efecto secundario**: Actualiza `breaker_state` gauge Prometheus a 1.
- **Restricción**: Cooldown anti-flapping; no reactiva si `now - last_activation < cooldown`.

### `async deactivate_breaker(breaker_type: str) -> bool`
- **Input**: `breaker_type` string.
- **Output**: `True` si se desactivó, `False` si tipo desconocido.
- **Efecto secundario**: Actualiza `breaker_state` gauge a 0.

### `is_breaker_active(breaker_type: str) -> bool`
- **Input**: `breaker_type` string.
- **Output**: `True`/`False`. Retorna `False` si tipo desconocido.

### `is_trading_halted() -> bool`
- **Output**: `True` si CUALQUIER breaker está activo.

### `get_all_breakers_status() -> Dict[str, Any]`
- **Output**: `{"critical_mode": bool, "active_breakers": [str], "total_active": int, "breakers": dict}`.

---

## 3. RiskManager (`app/core/risk_manager.py`)

### `calculate_dynamic_position_size(params: PositionSizeParams) -> float`
- **Input**: `PositionSizeParams` con `symbol`, `account_equity`, `atr`, `winrate_estimate`, `avg_win_loss_ratio`, `price`, y caps opcionales.
- **Output**: Tamaño de posición en USDT (float ≥ 0).
- **Lógica**: Intenta Kelly fraccional → Si no aplica → ATR sizing → Aplica límites.
- **Fallback**: `account_equity * 0.01` si todo falla.
- **Efecto**: Actualiza gauges `kelly_fraction_used`, `position_size_usdt`.

### `get_adaptive_trailing_stop(params: TrailingStopParams) -> float`
- **Input**: `TrailingStopParams` con `symbol`, `entry_price`, `atr`, `multiplier_atr`, `is_long`.
- **Output**: Precio del stop loss (float).
- **Efecto**: Almacena trailing stop en `self.trailing_stops[symbol]`.

### `update_trailing_stop(symbol: str, current_price: float) -> Optional[float]`
- **Input**: `symbol` string, `current_price` float.
- **Output**: Nuevo stop price si se actualizó, `None` si no.
- **Nota**: Para longs, solo mueve stop hacia arriba. Para shorts, solo hacia abajo.

### `check_circuit_breaker() -> BreakerState`
- **Output**: `BreakerState` ∈ {NORMAL, WARNING, DANGER, STOPPED}.
- **Efecto**: Incrementa `circuit_breaker_triggered` counter.

### `trigger_emergency_stop(reason: str) -> None`
- **Efecto**: `emergency_stop = True`, `breaker_state = STOPPED`.
- **Irreversible hasta**: `reset_emergency_stop()`.

---

## 4. OrderValidator (`app/services/order_validation.py`)

### `get_symbol_info(symbol: str) -> Optional[Dict]`
- **Input**: `symbol` string (e.g., "BTCUSDT").
- **Output**: Dict con `stepSize`, `minQty`, `maxQty`, `minNotional`, `tickSize`, `minPrice`, `maxPrice`, `pricePrecision`, `quantityPrecision`. `None` si error.
- **Cache**: Resultado cacheado en `_symbol_info_cache`.

### `validate_order_parameters(symbol, quantity, side, order_type, price) -> Dict`
- **Input**: symbol, quantity (float), side ("BUY"/"SELL"), order_type ("MARKET"/"LIMIT"), price (float, requerido para LIMIT).
- **Output**: `{"is_valid": bool, "errors": [str], "warnings": [str], "quantity_info": dict, "current_price": float, "adjusted_price": float, "notional_value": float, "recommended_quantity": float}`.
- **Validaciones**:
  1. Ajusta quantity a stepSize (ROUND_DOWN).
  2. Ajusta price a tickSize (ROUND_DOWN) si LIMIT.
  3. Verifica minQty ≤ qty ≤ maxQty.
  4. Verifica notional ≥ minNotional.
  5. Verifica precio en rango [minPrice, maxPrice].
- **Dependencia**: Llama a `client.get_symbol_ticker()` para precio actual.

### `place_market_order_with_validation(symbol, side, quantity) -> Dict`
- **Input**: symbol, side ("BUY"/"SELL"), quantity (float).
- **Output**: `{"order": dict, "validation": dict, "executed_quantity": float, "action_details": dict}`.
- **Errores**: `ValueError` si validación falla. `BinanceAPIException` formateada.

---

## 5. ReconciliationService (`app/services/reconciliation_service.py`)

### `__init__(client: Client, breakers: CircuitBreakers, threshold_pct: float = 0.01)`
- **Input**: cliente Binance, instancia de breakers, umbral relativo.

### `async run_reconciliation_cycle() -> Dict[str, Any]`
- **Output**: `{"status": "ok"|"error", "ext_usdt": float, "portfolio_total_usdt": float, "int_usdt": float, "discrepancy_usd": float, "latency_seconds": float}`.
- **Efecto**: Actualiza métricas `reconciliation_latency_seconds`, `balance_discrepancy_usd`, `unaccounted_pnl_usd`, `portfolio_total_value_usdt`, `cash_balance_usdt`.
- **Nota**: Actualmente `has_internal_accounting = False`, por lo que discrepancia siempre es 0.

### `async start(interval_seconds: int = 60) -> None`
- **Efecto**: Loop infinito que ejecuta `run_reconciliation_cycle()` cada `interval_seconds`.
- **Idempotencia**: Si `_running == True`, retorna inmediatamente.

---

## 6. StrategySelector (`app/services/strategy_selector.py`)

### `select_strategy(regime_prediction, symbol, account_state) -> StrategySpec`
- **Input**: `RegimePrediction`, `symbol` string, `AccountState`.
- **Output**: `StrategySpec` con `strategy_name` (StrategyType), `params` (StrategyParams), `confidence` (0-1), `reasoning` (str).
- **Lógica de selección**:
  1. Si `emergency_stop` → HOLD (confianza 1.0).
  2. Determinar volatilidad → buscar config por (régimen, volatilidad).
  3. Calcular params dinámicos vía Kelly fraccional.
  4. Ajustar confianza: risk_score > 0.8 → ×0.69; daily_pnl < -5% → ×0.49.
  5. Si BULL_TREND en ambos horizontes + confianza ≥ 0.7 → DCA.
- **Fallback**: HOLD (confianza 0.5) si error.
- **Efecto**: Actualiza métricas `strategy_selections_total`, `strategy_confidence`.

### AccountState (Input Schema)
```python
class AccountState(BaseModel):
    total_equity: float
    available_balance: float
    total_exposure: float
    daily_pnl: float
    max_drawdown: float
    risk_score: float
```

### StrategyType (Output Enum)
```python
class StrategyType(Enum):
    GRID_TRADING = "GridTrading"
    DCA = "DCA"
    SCALPING = "Scalping"
    HOLD = "HOLD"
    HEDGING = "Hedging"
```

---

## 7. MLEngine (`app/services/ml_engine.py`)

### `async predict_regime(symbol, interval, limit) -> RegimePrediction`
- **Input**: `symbol` string, `interval` string (default "1m"), `limit` int (default 60).
- **Output**: `RegimePrediction(label: int, proba: float)`.
- **Fallback**: `RegimePrediction(label=0, proba=0.5)` si pipeline es None o predicción falla.

### `async train_on_symbol(symbol, interval, limit) -> None`
- **Efecto**: Entrena incrementalmente el modelo River con klines recientes.
- **No-op**: Si `self.pipeline is None`.

### `async compute_features_from_klines(klines) -> Dict[str, float]`
- **Output**: `{"volatility": float, "spread": float, "volume": float, "rsi": float, "atr": float}`.
- **Fallback vacío**: `{"volatility": 0.0, "spread": 0.0, "volume": 0.0, "rsi": 50.0, "atr": 0.0}`.

---

## 8. HybridMLEngine (`app/services/hybrid_ml_engine.py`)

### `async predict_regime(symbol, recent_data, current_features) -> RegimePrediction`
- **Input**: `symbol` string, `recent_data` DataFrame, `current_features` Dict[str, float].
- **Output**: `RegimePrediction(long_regime, short_regime, long_conf, short_conf)`.
- **Fallback**: `RANGE` para ambos con `conf=0.5`.

### `async train_deep_model(history_df, symbol, output_path, config) -> str`
- **Output**: Ruta del modelo guardado.
- **Error**: `ValueError` si datos insuficientes (< 100 muestras).

---

## 9. TradeExecutor (`app/services/trade_executor.py`)

### `execute_order(symbol, side, order_type, quantity, db, update_balance, **kwargs) -> Dict`
- **Input**: `symbol` str, `side` "BUY"/"SELL", `order_type` str, `quantity` str, opcionales.
- **Output**: Respuesta de Binance.
- **Efecto**: Actualiza balances internos si `update_balance=True`.
- **Mitigación**: Reintento automático en error `-1021` (timestamp sync).

---

## 10. IntegrityGuardMiddleware (`app/core/middleware/integrity_guard.py`)

### `async dispatch(request, call_next) -> Response`
- **Input**: HTTP request.
- **Output**: Response normal o HTTP 503 JSON.
- **Lógica**:
  1. Bypass en tests (`PYTEST_CURRENT_TEST`) o si `DISABLE_INTEGRITY_GUARD=true`.
  2. GET/HEAD/OPTIONS → pass-through.
  3. POST/PUT/DELETE en rutas protegidas (`/api/trade`, `/api/strategies`) → consulta breakers → 503 si activos.

---

## 11. Celery Tasks (`app/services/trading_tasks.py`)

### `trading_cycle_tick` (cada 60s)
- **Responsabilidad**: Orquesta el ciclo de trading de 5 minutos.
- **Dependencias**: MLEngine, StrategySelector, RiskManager, TradeExecutor.
- **Parámetros clave**: `MIN_DECISION_CONFIDENCE = 0.50`, `MIN_NOTIONAL_USDT = 10.5`, `SAFE_MIN_USDT = 15.0`.

### `dust_sweep` (domingos 03:00 UTC)
- **Responsabilidad**: Barrer activos con valor < 1 USDT.
- **Default**: `dry_run=True`.
- **Cola**: `low`.

---

## 12. Auth (`app/core/auth.py`)

### `require_auth(api_key: str) -> str`
- **Input**: Header `Authorization: Bearer <token>`.
- **Output**: Token string si válido.
- **Errores**: HTTP 401 si ausente, malformado o inválido.
- **Token válido**: `API_KEY` env var o fallback `gridbot_api_key_2024_secure_12345`.

---

## 13. Config (`app/core/config.py`)

### `Settings`
- **Campos clave**: `database_url`, `redis_url`, `binance_api_key`, `binance_api_secret`, `paper_trading`, `binance_testnet`, `secret_key`, `debug`.
- **Auto-detección**: Docker vs local vs Heroku.
- **Validación producción**: `SECRET_KEY` obligatorio, `DEBUG=false`.
- **Singleton**: `settings = Settings()` al importar.

---

## 14. Schemas de Validación (`app/schemas/validation.py`)

### `OrderRequest`
```python
symbol: str  # [A-Z0-9]+, 1-20 chars
side: str    # "BUY" | "SELL"
quantity: float  # > 0, <= 1000
type: str    # "MARKET" | "LIMIT"
price: Optional[float]  # > 0, requerido si type="LIMIT"
```

### `GridParams`
```python
symbol: str
min_price: float  # > 0, <= 1000000
max_price: float  # > min_price, <= 1000000
grids: int        # > 1, <= 100
quantity: float   # > 0, <= 1000
last_action: Optional[str]  # "BUY" | "SELL" | None
```

### `StrategyParams`
```python
symbol: str
interval: str       # valid kline intervals
limit: int          # > 0, <= 1000
balances: Dict[str, float]  # no negativos
params: Dict[str, Any]
```
