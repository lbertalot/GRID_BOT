# GridBot v2.5 - Lógica de Trading y Matemática

> **Última actualización**: 2026-01-02
> **Auditor**: Senior Software Architect & Trading Systems Specialist
> **Versión**: 2.5.0

## 📐 Visión General

GridBot v2.5 implementa un sistema de **Trading Algorítmico Multi-Estrategia** con:
- **Grid Trading** (estrategia principal)
- **Scalping** (alta frecuencia)
- **RSI/MACD** (indicadores técnicos)
- **ML Híbrido** (LSTM + River ML)

El ciclo de decisión es de **5 minutos** (4min evaluación, 1min ejecución) con validaciones multi-capa y sizing adaptativo basado en **Kelly Criterion Fraccional**.

---

## 🔄 Ciclo de Trading: Arquitectura Temporal

### Fase 1: Evaluación (0-240 segundos)

```
┌─────────────────────────────────────────────────────────┐
│  FASE DE EVALUACIÓN (4 minutos)                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  t=0s    ┌──────────────┐                               │
│          │ Market Data  │  Fetch precio, klines        │
│          │  Collector   │  (REST API Binance)          │
│          └──────┬───────┘                               │
│                 │                                        │
│  t=30s   ┌──────▼──────────┐                            │
│          │  ML Engine      │  LSTM: predict próximo    │
│          │  (LSTM + River) │  River: online learning   │
│          └──────┬──────────┘                            │
│                 │                                        │
│  t=60s   ┌──────▼───────────┐                           │
│          │ Strategy Selector│  Evalúa régimen mercado  │
│          │                  │  Selecciona estrategia    │
│          └──────┬───────────┘  Confidence score       │
│                 │                                        │
│  t=90s   ┌──────▼──────────┐                            │
│          │  Risk Manager   │  Kelly sizing             │
│          │                 │  Stop-loss calculation    │
│          └──────┬──────────┘                            │
│                 │                                        │
│  t=120s  ┌──────▼─────────┐                             │
│          │ Order Validator │  PRICE_FILTER             │
│          │                 │  LOT_SIZE                 │
│          │                 │  MIN_NOTIONAL             │
│          └──────┬──────────┘                            │
│                 │                                        │
│  t=180s  ┌──────▼────────────┐                          │
│          │ Circuit Breakers  │  Check estado breakers  │
│          │   Check           │  Balance discrepancy    │
│          └──────┬────────────┘                          │
│                 │                                        │
│  t=240s  ┌──────▼───────────┐                           │
│          │   DECISIÓN FINAL │  Go/No-Go para ejecutar  │
│          │   confidence >= 0│  .50                     │
│          └──────────────────┘                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Fase 2: Ejecución (240-300 segundos)

```
┌─────────────────────────────────────────────────────────┐
│  FASE DE EJECUCIÓN (1 minuto)                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  t=240s  ┌──────────────┐                               │
│          │ Check Breakers│  Final safety check         │
│          └──────┬────────┘                               │
│                 │                                        │
│  t=245s  ┌──────▼───────────┐                           │
│          │  Place Order     │  create_order(symbol,    │
│          │  (Binance API)   │    side, quantity)       │
│          └──────┬───────────┘                           │
│                 │                                        │
│  t=250s  ┌──────▼──────────┐                            │
│          │ Record in DB    │  Insert into trades      │
│          │                 │  Update balances         │
│          └──────┬──────────┘                            │
│                 │                                        │
│  t=255s  ┌──────▼──────────┐                            │
│          │ Update Metrics  │  Prometheus counters     │
│          │                 │  Grafana dashboards      │
│          └─────────────────┘                            │
│                                                          │
│  t=300s  ┌──────────────────┐                           │
│          │ Cycle Complete   │  Reset state             │
│          │                  │  Start new cycle         │
│          └──────────────────┘                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Implementación en Código**:
```python
# app/services/trading_tasks.py:101
@celery_app.task
def trading_cycle_tick():
    state = await _get_cycle_state()
    now = datetime.utcnow()
    elapsed = (now - started_at).total_seconds()

    if elapsed < 240:  # Evaluación
        cycle_phase.labels(phase="evaluation").set(_now_ts())
        # ... recolectar datos, ML, decisión
    elif elapsed < 300:  # Ejecución
        cycle_phase.labels(phase="execution").set(_now_ts())
        decision = state.get("decision")
        if decision and decision["confidence"] >= MIN_DECISION_CONFIDENCE:
            # ... ejecutar orden
    else:  # Reset
        await _set_cycle_state({"started_at": now.isoformat(), "decision": None})
```

**🔴 Problema Crítico**: Sin lock distribuido, si un ciclo tarda >60s se solapa con el siguiente.

---

## 🎯 Estrategia 1: Grid Trading

### Concepto

Grid Trading divide un rango de precios en "grillas" (niveles) y coloca órdenes de compra/venta en cada nivel:

```
Precio
  │
  │                    SELL │ 2400 USDT
  │  ─────────────────────────────────────
  │                    SELL │ 2380 USDT
  │  ─────────────────────────────────────
  │         PRECIO ACTUAL → │ 2350 USDT
  │  ─────────────────────────────────────
  │                    BUY  │ 2320 USDT
  │  ─────────────────────────────────────
  │                    BUY  │ 2300 USDT
  │
  └──────────────────────────────────────► Tiempo
```

### Parámetros de Grid

```python
# app/services/grid_strategy.py
class GridConfig:
    upper_price: Decimal      # Precio máximo del grid
    lower_price: Decimal      # Precio mínimo del grid
    grid_levels: int = 10     # Cantidad de niveles
    quantity_per_level: Decimal  # Cantidad por orden

    # Calculados
    @property
    def price_step(self) -> Decimal:
        return (self.upper_price - self.lower_price) / self.grid_levels
```

### Matemática de Grid

#### 1. Cálculo de Niveles

Para un grid con:
- `upper_price = 2400`
- `lower_price = 2300`
- `grid_levels = 10`

```python
price_step = (2400 - 2300) / 10 = 10 USDT

levels = [
    2300,  # Nivel 0 (BUY)
    2310,  # Nivel 1 (BUY)
    2320,  # Nivel 2 (BUY)
    ...
    2390,  # Nivel 9 (SELL)
    2400   # Nivel 10 (SELL)
]
```

#### 2. Profit por Trade

```
Profit = price_step × quantity - (2 × commission)
```

Ejemplo:
- Compra en 2300 USDT, vende en 2310 USDT
- Cantidad: 0.01 ETH
- Comisión: 0.1% = 0.001

```
Gross Profit = (2310 - 2300) × 0.01 = 0.10 USDT
Commission = (2300 × 0.01 × 0.001) + (2310 × 0.01 × 0.001) = 0.0461 USDT
Net Profit = 0.10 - 0.0461 = 0.0539 USDT ≈ 0.23% ROI por trade
```

#### 3. Capital Allocation

Para N niveles de grid con precio promedio `P_avg`:

```
Capital Total = Σ(quantity_per_level × price_i)
              = quantity_per_level × Σ(price_i)
              = quantity_per_level × N × P_avg
```

**🔴 Problema Identificado** (línea `grid_strategy.py:~85`):
```python
# Capital allocation no verifica balance total antes de calcular grid
total_required = sum([level.price * level.quantity for level in grid_levels])
# ⚠️ Si total_required > available_balance, se generan órdenes inválidas
```

---

## 📊 Estrategia 2: Scalping

### Concepto

Scalping busca pequeños movimientos de precio (0.1%-0.5%) con alta frecuencia:

```
Precio
  │
  │              ┌─────┐  SELL +0.3%
  │     ┌────────┘     └────────┐
  │  ───┘ BUY                   └─── BUY
  │
  └──────────────────────────────────► Tiempo (minutos)
```

### Parámetros

```python
# app/services/strategies/scalping.py
class ScalpingConfig:
    profit_target_pct: float = 0.003  # 0.3% target
    stop_loss_pct: float = 0.001      # 0.1% stop
    max_holding_time_seconds: int = 300  # 5 minutos max
    min_spread_pct: float = 0.0001    # 0.01% spread mínimo
```

### Matemática de Scalping

#### 1. Entry Logic

```python
def should_enter_scalp(current_price, bid, ask, volume_24h):
    spread = (ask - bid) / current_price

    # Condiciones:
    # 1. Spread suficiente para cubrir comisiones
    if spread < min_spread_pct + (2 * commission_rate):
        return False

    # 2. Volumen suficiente para liquidez
    if volume_24h < min_volume_threshold:
        return False

    # 3. Momentum positivo (RSI entre 30-70)
    rsi = calculate_rsi(prices[-14:])
    if not (30 < rsi < 70):
        return False

    return True
```

#### 2. Exit Logic

```python
def should_exit_scalp(entry_price, current_price, entry_time):
    pnl_pct = (current_price - entry_price) / entry_price
    elapsed = time.time() - entry_time

    # Exit si:
    # 1. Alcanza profit target
    if pnl_pct >= profit_target_pct:
        return True, "PROFIT_TARGET"

    # 2. Alcanza stop loss
    if pnl_pct <= -stop_loss_pct:
        return True, "STOP_LOSS"

    # 3. Timeout (holding demasiado tiempo)
    if elapsed > max_holding_time_seconds:
        return True, "TIMEOUT"

    return False, None
```

**⚠️ Riesgo**: Scalping en mercados de baja liquidez puede generar slippage que elimine el profit.

---

## 📈 Estrategia 3: RSI/MACD

### Concepto

Usa indicadores técnicos tradicionales:

**RSI (Relative Strength Index)**:
- Mide fuerza de movimientos de precio (0-100)
- < 30: Oversold (señal de compra)
- \> 70: Overbought (señal de venta)

**MACD (Moving Average Convergence Divergence)**:
- Crossover de medias móviles
- MACD > Signal: Bullish (compra)
- MACD < Signal: Bearish (venta)

### Matemática de RSI

```
RSI = 100 - (100 / (1 + RS))

donde:
RS = Average Gain / Average Loss (últimos 14 periodos)

Average Gain = Σ(gains) / 14
Average Loss = Σ(losses) / 14
```

**Implementación**:
```python
# app/services/strategies/rsi_macd.py
def calculate_rsi(prices: List[float], period: int = 14) -> float:
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi
```

### Matemática de MACD

```
EMA_12 = Exponential Moving Average (12 periodos)
EMA_26 = Exponential Moving Average (26 periodos)

MACD Line = EMA_12 - EMA_26
Signal Line = EMA(MACD Line, 9 periodos)
Histogram = MACD Line - Signal Line
```

**Señales**:
- `Histogram > 0` y cruzando hacia arriba: **BUY**
- `Histogram < 0` y cruzando hacia abajo: **SELL**

```python
def calculate_macd(prices: List[float]) -> Dict:
    ema_12 = calculate_ema(prices, 12)
    ema_26 = calculate_ema(prices, 26)

    macd_line = ema_12 - ema_26
    signal_line = calculate_ema(macd_line, 9)
    histogram = macd_line - signal_line

    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram
    }
```

---

## 🤖 ML Engine (Híbrido)

### Arquitectura de ML

```
┌──────────────────────────────────────────┐
│         ML Híbrido                       │
├──────────────────────────────────────────┤
│                                          │
│  ┌────────────────┐  ┌────────────────┐ │
│  │  LSTM Model    │  │  River ML      │ │
│  │  (Long-term)   │  │  (Short-term)  │ │
│  │                │  │                │ │
│  │ Predice precio │  │ Online learning│ │
│  │ próximos 15min │  │ adapta en vivo │ │
│  └────────┬───────┘  └────────┬───────┘ │
│           │                   │         │
│           └───────┬───────────┘         │
│                   │                     │
│           ┌───────▼────────┐            │
│           │  Ensemble      │            │
│           │  Combina ambos │            │
│           │  70% LSTM      │            │
│           │  30% River     │            │
│           └────────────────┘            │
│                                          │
└──────────────────────────────────────────┘
```

### LSTM: Predicción de Precio

**Modelo**:
```python
# app/services/ml_engine.py
class LSTMPricePredictor:
    def __init__(self):
        self.model = Sequential([
            LSTM(50, return_sequences=True, input_shape=(lookback, features)),
            Dropout(0.2),
            LSTM(50, return_sequences=False),
            Dropout(0.2),
            Dense(25),
            Dense(1)
        ])
        self.model.compile(optimizer='adam', loss='mse')
```

**Input**: Últimas 60 velas (1h de datos en timeframe 1min)
**Output**: Precio predicho en 15 minutos

**Features**:
- `price_close`
- `volume`
- `rsi_14`
- `macd`
- `bollinger_upper`
- `bollinger_lower`

**Matemática**:
```
LSTM Cell:
f_t = σ(W_f · [h_{t-1}, x_t] + b_f)  # Forget gate
i_t = σ(W_i · [h_{t-1}, x_t] + b_i)  # Input gate
o_t = σ(W_o · [h_{t-1}, x_t] + b_o)  # Output gate
C_t = f_t * C_{t-1} + i_t * tanh(W_C · [h_{t-1}, x_t] + b_C)
h_t = o_t * tanh(C_t)

donde σ = función sigmoide
```

**🔴 Problema** (línea `ml_engine.py:~120`):
```python
# Modelo LSTM se carga en __init__ de forma SÍNCRONA
self.model = tf.keras.models.load_model("lstm_model.h5")
# ⚠️ Bloquea el event loop si el modelo es grande
```

### River ML: Online Learning

**Modelo**:
```python
# app/services/hybrid_ml_engine.py
from river import linear_model, preprocessing

class RiverOnlineLearner:
    def __init__(self):
        self.model = (
            preprocessing.StandardScaler() |
            linear_model.LinearRegression()
        )

    def partial_fit(self, x, y):
        self.model.learn_one(x, y)

    def predict(self, x):
        return self.model.predict_one(x)
```

**Ventajas**:
- Aprende de cada trade sin reentrenamiento completo
- Se adapta a cambios de régimen de mercado
- Memoria baja (no guarda histórico completo)

**Matemática (Linear Regression Online)**:
```
y_pred = w₀ + w₁x₁ + w₂x₂ + ... + wₙxₙ

Update de pesos:
w_i := w_i + α(y_actual - y_pred) * x_i

donde α = learning rate
```

---

## 💰 Position Sizing: Kelly Criterion

### Kelly Fraccional

```
Kelly % = (p × (b + 1) - 1) / b

donde:
p = win rate (probabilidad de ganar)
b = ratio win/loss (avg_win / avg_loss)

Kelly Fraccional = Kelly % × fraction  # fraction = 0.25 por seguridad
```

**Implementación**:
```python
# app/core/risk_manager.py:45
def calculate_kelly_size(win_rate, avg_win, avg_loss, balance, fraction=0.25):
    if avg_loss == 0:
        return 0

    b = avg_win / avg_loss
    kelly_pct = (win_rate * (b + 1) - 1) / b

    # Protección contra Kelly negativo o excesivo
    kelly_pct = max(0, min(kelly_pct, 0.25))  # Max 25% del balance

    fractional_kelly = kelly_pct * fraction

    position_size_usdt = balance * fractional_kelly

    return position_size_usdt
```

**Ejemplo**:
- `win_rate = 0.60` (60% de trades ganadores)
- `avg_win = 5 USDT`
- `avg_loss = 3 USDT`
- `balance = 100 USDT`
- `fraction = 0.25`

```
b = 5 / 3 = 1.67
kelly_pct = (0.60 × (1.67 + 1) - 1) / 1.67
          = (0.60 × 2.67 - 1) / 1.67
          = (1.60 - 1) / 1.67
          = 0.36  (36%)

fractional_kelly = 0.36 × 0.25 = 0.09  (9%)

position_size = 100 × 0.09 = 9 USDT
```

**🔴 Problema**: No considera correlación entre posiciones (varias posiciones en ETH pueden superar límite de riesgo total).

---

## 🛡️ Risk Management: Stop Loss y Trailing Stop

### Stop Loss Fijo

```python
def check_stop_loss(entry_price, current_price, stop_loss_pct):
    pnl_pct = (current_price - entry_price) / entry_price

    if pnl_pct <= -stop_loss_pct:
        return True, "STOP_LOSS_TRIGGERED"

    return False, None
```

### Trailing Stop (Adaptativo)

```python
# app/services/strategies/trailing_stop.py
class TrailingStop:
    def __init__(self, initial_stop_pct, trail_pct):
        self.initial_stop_pct = initial_stop_pct  # 2%
        self.trail_pct = trail_pct  # 0.5%
        self.highest_price = None

    def update(self, entry_price, current_price):
        if self.highest_price is None or current_price > self.highest_price:
            self.highest_price = current_price

        # Stop loss inicial (desde entry)
        initial_stop = entry_price * (1 - self.initial_stop_pct)

        # Trailing stop (desde highest price)
        trailing_stop = self.highest_price * (1 - self.trail_pct)

        # Usar el más alto de los dos
        effective_stop = max(initial_stop, trailing_stop)

        if current_price <= effective_stop:
            return True, "TRAILING_STOP_TRIGGERED"

        return False, None
```

**Ejemplo Visual**:
```
Precio
  │
  │              ┌──── Highest = 2400
  │             /│\
  │            / │ \
  │           /  │  \   Trailing Stop = 2400 × 0.995 = 2388
  │          /   │   ─────────────────────────────
  │         /    │      \
  │  Entry ─     │       \
  │  2300        │        └─── Sell Triggered!
  │              │
  └──────────────┼────────────────────────────► Tiempo
                 │
            Initial Stop = 2300 × 0.98 = 2254
```

---

## 🔍 Order Validation: Multi-Layer

### Layer 1: Exchange Filters (Binance)

```python
# app/services/order_validation.py:35
def validate_against_exchange_info(symbol, price, quantity):
    filters = get_symbol_filters(symbol)  # Desde exchange_info

    # PRICE_FILTER
    price_filter = filters['PRICE_FILTER']
    min_price = Decimal(price_filter['minPrice'])
    max_price = Decimal(price_filter['maxPrice'])
    tick_size = Decimal(price_filter['tickSize'])

    if not (min_price <= price <= max_price):
        raise ValidationError(f"Price {price} fuera de rango [{min_price}, {max_price}]")

    # Ajustar a tick_size
    price = (price // tick_size) * tick_size

    # LOT_SIZE
    lot_filter = filters['LOT_SIZE']
    min_qty = Decimal(lot_filter['minQty'])
    max_qty = Decimal(lot_filter['maxQty'])
    step_size = Decimal(lot_filter['stepSize'])

    if not (min_qty <= quantity <= max_qty):
        raise ValidationError(f"Quantity {quantity} fuera de rango [{min_qty}, {max_qty}]")

    # Ajustar a step_size
    quantity = (quantity // step_size) * step_size

    # MIN_NOTIONAL
    notional_filter = filters['MIN_NOTIONAL']
    min_notional = Decimal(notional_filter['minNotional'])
    notional = price * quantity

    if notional < min_notional:
        raise ValidationError(f"Notional {notional} < {min_notional}")

    return price, quantity
```

### Layer 2: Balance Check

```python
def validate_balance(symbol, side, quantity, price):
    balances = get_balances()

    if side == "BUY":
        required_usdt = quantity * price
        commission = required_usdt * 0.001  # 0.1%
        total_required = required_usdt + commission

        if balances['USDT'] < total_required:
            raise InsufficientBalanceError(f"Need {total_required} USDT, have {balances['USDT']}")

    elif side == "SELL":
        asset = symbol.replace("USDT", "")
        if balances.get(asset, 0) < quantity:
            raise InsufficientBalanceError(f"Need {quantity} {asset}, have {balances.get(asset, 0)}")
```

### Layer 3: Circuit Breakers

```python
def validate_circuit_breakers():
    breakers = get_breakers_status()

    if breakers['balance_discrepancy']['active']:
        raise CircuitBreakerError("Balance discrepancy breaker activo")

    if breakers['system_integrity']['active']:
        raise CircuitBreakerError("System integrity breaker activo")

    if breakers['critical_mode']['active']:
        raise CircuitBreakerError("CRITICAL MODE - Trading disabled")
```

**🔴 Problema**: Estas 3 validaciones no son atómicas. Entre validación y ejecución pueden cambiar condiciones.

---

## 📊 Performance Metrics

### Métricas Calculadas

```python
# app/services/metrics_service.py
def calculate_portfolio_metrics():
    trades = get_all_trades()

    # PnL Total
    total_pnl = sum([t.realized_pnl for t in trades if t.status == 'CLOSED'])

    # Win Rate
    winning_trades = [t for t in trades if t.realized_pnl > 0]
    win_rate = len(winning_trades) / len(trades) if trades else 0

    # Average Win/Loss
    avg_win = sum([t.realized_pnl for t in winning_trades]) / len(winning_trades) if winning_trades else 0
    losing_trades = [t for t in trades if t.realized_pnl < 0]
    avg_loss = abs(sum([t.realized_pnl for t in losing_trades]) / len(losing_trades)) if losing_trades else 0

    # Sharpe Ratio (aproximado)
    returns = [t.realized_pnl / t.cost_basis for t in trades if t.status == 'CLOSED']
    sharpe = (mean(returns) - risk_free_rate) / std(returns) if std(returns) > 0 else 0

    # Max Drawdown
    cumulative_pnl = cumsum([t.realized_pnl for t in trades])
    running_max = cummax(cumulative_pnl)
    drawdown = running_max - cumulative_pnl
    max_drawdown = max(drawdown)

    return {
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown
    }
```

---

## 🚦 Recomendaciones de Trading Logic

### Prioridad Alta

1. **Implementar WebSocket para fills**: Actualizar trades en tiempo real
2. **Atomic Order Execution**: Validación + ejecución en transacción atómica
3. **Position Correlation Matrix**: Evitar sobre-exposición en assets correlacionados

### Prioridad Media

4. **Dynamic Stop Loss**: Ajustar stop según volatilidad (ATR-based)
5. **Multi-Timeframe Analysis**: Confirmar señales en múltiples timeframes
6. **Backtest Framework**: Validar estrategias antes de producción

### Prioridad Baja

7. **Sentiment Analysis**: Integrar noticias/twitter para señales
8. **Portfolio Rebalancing**: Ajustar weights de posiciones periódicamente
9. **Tax Loss Harvesting**: Optimizar impuestos en jurisdicciones aplicables

---

## 📚 Referencias

- [Kelly Criterion](https://en.wikipedia.org/wiki/Kelly_criterion)
- [LSTM Networks](https://colah.github.io/posts/2015-08-Understanding-LSTMs/)
- [Binance API Filters](https://binance-docs.github.io/apidocs/spot/en/#filters)
- [Technical Analysis Library](https://technical-analysis-library-in-python.readthedocs.io/)
