### Backtesting Service

Location: `app/services/backtesting_service.py`

Purpose
- VectorBT-based simulation with walk-forward capability and synthetic data fallback.
- Produces `BacktestResult` Pydantic objects and Prometheus metrics.

Config and result models
- `BacktestConfig`: `{initial_capital, commission, slippage, walk_forward, window_size, step_size, min_samples}`
- `BacktestResult`: `{symbol, strategy_hash, start_date, end_date, initial_capital, final_capital, total_return, max_drawdown, sharpe_ratio, sortino_ratio, win_rate, profit_factor, total_trades, avg_trade_duration, metrics_json, backtest_ts}`

Key methods
- `async download_ohlcv_data(symbol, start_date, end_date) -> pd.DataFrame`
- `async run_backtest(strategy_spec, symbol, start_date, end_date, initial_capital: Optional[float] = None, config: Optional[BacktestConfig] = None) -> BacktestResult`
- `async run_walk_forward_backtest(strategy_spec, symbol, start_date, end_date, config: Optional[BacktestConfig] = None) -> List[BacktestResult]`
- `save_backtest_results(results, filename: Optional[str] = None) -> str`
- `load_backtest_results(filepath: str) -> List[BacktestResult]`
- `get_backtest_summary(results: List[BacktestResult]) -> Dict[str, Any]`

Usage example
```python
import asyncio
from datetime import datetime, timedelta
from app.services.backtesting_service import BacktestingService, BacktestConfig
from app.services.strategy_selector import StrategySpec, StrategyParams, StrategyType
from app.core.risk_manager import RegimePrediction, MarketRegime

async def main():
    b = BacktestingService()
    # Minimal strategy spec (parameters interpreted by simulator helpers)
    spec = StrategySpec(
        strategy_name=StrategyType.GRID_TRADING,
        params=StrategyParams(grid_spacing_bps=50, grid_levels=10, order_size_usdt=50.0),
        confidence=0.7,
        reasoning="test",
        regime_prediction=RegimePrediction(long_regime=MarketRegime.RANGE, short_regime=MarketRegime.RANGE, long_conf=0.7, short_conf=0.7)
    )

    start = datetime.utcnow() - timedelta(days=30)
    end = datetime.utcnow()

    result = await b.run_backtest(spec, "BNBUSDT", start, end, config=BacktestConfig(min_samples=100))
    print(result.total_return, result.sharpe_ratio)

asyncio.run(main())
```

Metrics
- `backtest_runs_total{symbol,strategy}`
- `backtest_duration_seconds{symbol,strategy}`
- `backtest_metrics{symbol,strategy,metric}`