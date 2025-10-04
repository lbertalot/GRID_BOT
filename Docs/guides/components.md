### Core Components and Services

This section documents the main functional services that interact with ML and strategies.

#### Risk types and manager
Location: `app/core/risk_manager.py`

- `MarketRegime` (Enum): `BULL_TREND, BEAR_TREND, RANGE, HIGH_VOL, CRASH_IMMINENT, HIGH_VOLATILITY_BEAR`
- `RegimePrediction` (Pydantic): `{long_regime: MarketRegime, short_regime: MarketRegime, long_conf: float, short_conf: float, timestamp}`
- Kelly sizing
  - `PositionSizeParams`: inputs for ATR/Kelly sizing
  - `calculate_dynamic_position_size(params) -> float`: returns USDT size after limits and regime multipliers
- Adaptive trailing stop
  - `get_adaptive_trailing_stop(params: TrailingStopParams) -> float`
  - `update_trailing_stop(symbol, current_price) -> Optional[float]`
- Circuit breaker and metrics
  - `apply_market_regime_filter(regime)`; `check_circuit_breaker()`; `get_risk_status()`; `update_metrics()`

Usage snippet
```python
from app.core.risk_manager import RiskManager, PositionSizeParams, MarketRegime

rm = RiskManager()
rm.apply_market_regime_filter(MarketRegime.RANGE)
size = rm.calculate_dynamic_position_size(PositionSizeParams(
    symbol="BNBUSDT", account_equity=10_000, atr=0.02, winrate_estimate=0.55, avg_win_loss_ratio=1.6, price=600
))
print(size)
```

#### Strategy selection
Location: `app/services/strategy_selector.py`

- `StrategyType`: `GRID_TRADING, DCA, SCALPING, HOLD, HEDGING`
- `StrategyParams` (dataclass): strategy-specific parameters
- `StrategySpec` (Pydantic): `{strategy_name, params, confidence, reasoning, regime_prediction, timestamp}`
- `AccountState` (Pydantic): account-level context for risk and sizing
- `StrategySelector(risk_manager)`
  - `select_strategy(regime_prediction, symbol, account_state) -> StrategySpec`
  - Internally adjusts parameters via Kelly/ATR sizing and regime-driven spacing.

Usage snippet
```python
from app.services.strategy_selector import StrategySelector, AccountState
from app.core.risk_manager import RiskManager, RegimePrediction, MarketRegime

selector = StrategySelector(RiskManager())
rp = RegimePrediction(long_regime=MarketRegime.RANGE, short_regime=MarketRegime.RANGE, long_conf=0.6, short_conf=0.65)
spec = selector.select_strategy(rp, "BTCUSDT", AccountState(
    total_equity=10_000, available_balance=8_000, total_exposure=0.3, daily_pnl=0.0, max_drawdown=0.1, risk_score=0.2
))
print(spec.strategy_name.value, spec.params)
```

#### Market data collection
Location: `app/services/market_data_collector.py`

- `MarketDataCollector(ttl_seconds: int = 5)`
  - `await get_price(symbol) -> float`
  - `await get_klines(symbol, interval = "1m", limit = 120) -> List[List[Any]]`
  - `await validate_order(symbol, quantity, order_type = "MARKET", price: Optional[float]) -> Dict`
  - `await save_klines_to_db(symbol, interval, klines) -> int`

Usage snippet
```python
import asyncio
from app.services.market_data_collector import MarketDataCollector

async def main():
    c = MarketDataCollector()
    price = await c.get_price("ETHUSDT")
    klines = await c.get_klines("ETHUSDT", "1m", 60)
    print(price, len(klines))

asyncio.run(main())
```

#### Performance analysis
Location: `app/services/performance_analyzer.py`

- `PerformanceAnalyzer`
  - `async calculate_comprehensive_metrics(days: int = 30) -> PerformanceMetrics`
  - `async get_asset_performance(symbol: str, days: int = 30) -> Dict`
  - `async get_portfolio_allocation() -> Dict`
- `PerformanceMetrics` (dataclass): includes `total_return, sharpe_ratio, max_drawdown, volatility, win_rate, profit_factor, ...`

Usage snippet
```python
import asyncio
from app.services/performance_analyzer import performance_analyzer

async def main():
    metrics = await performance_analyzer.calculate_comprehensive_metrics(days=30)
    print(metrics.sharpe_ratio, metrics.max_drawdown)

asyncio.run(main())
```

#### Grid helper
Location: `app/services/grid_strategy.py`

- `calculate_grid_levels(min_price, max_price, grids) -> List[float]`
- `decide_grid_action(current_price, grid_levels, last_action=None) -> Dict`


