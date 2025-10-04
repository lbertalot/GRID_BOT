### MLEngine (Online, Incremental)

Location: `app/services/ml_engine.py`

Purpose
- Online regime classification with minimal latency and footprint using River.
- Extracts features from recent klines, trains incrementally, detects drift, and predicts 0/1 regime.

Types
- `RegimePrediction` (dataclass): `{label: int, proba: float}`

API
- `MLEngine(model_path: Optional[str] = None)`
  - Loads existing pipeline from `model_path` (env `ML_MODEL_PATH`) via joblib if present; otherwise initializes StandardScaler | LogisticRegression when River is available.
- `await save_model() -> None`
  - Persists pipeline to `model_path` using `asyncio.to_thread`.
- `await compute_features_from_klines(klines: List[List[Any]]) -> Dict[str, float]`
  - Returns `{volatility, spread, volume, rsi, atr}` from Binance klines `[open, high, low, close, volume, ...]`.
- `await train_on_symbol(symbol: str, interval: str = "1m", limit: int = 60) -> None`
  - Fetches klines via `MarketDataCollector`, computes features, derives heuristic label from recent trend, updates drift detector (ADWIN), and calls `learn_one`.
- `await predict_regime(symbol: str, interval: str = "1m", limit: int = 60) -> RegimePrediction`
  - Computes features and returns probabilistic label. If River unavailable, returns `(0, 0.5)`.

Feature definitions
- volatility: std deviation of percentage returns over window
- spread: mean relative range (high - low) / close
- volume: mean volume
- rsi: RSI over recent closes (reused from `rsi_macd` util)
- atr: average true range approximation (TR over window)

Usage example
```python
import asyncio
from app.services.ml_engine import MLEngine

async def run():
    engine = MLEngine()
    # Predict
    pred = await engine.predict_regime(symbol="BNBUSDT", interval="1m", limit=60)
    print({"label": pred.label, "proba": pred.proba})

    # Train incrementally (safe to call often)
    await engine.train_on_symbol("BNBUSDT", "1m", 60)
    await engine.save_model()

asyncio.run(run())
```

Integration notes
- `MarketDataCollector` handles caching and rate-limiting to minimize exchange load.
- Drift handling: `ADWIN` reset of the metric on detected change; you can externalize this signal to adjust strategy confidence.
- This engine produces a simplified prediction. If you need long/short horizon regimes for `StrategySelector`, use `HybridMLEngine`.


