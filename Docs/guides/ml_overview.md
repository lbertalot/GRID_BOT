### Machine Learning Overview

This project implements predictive and adaptive market regime detection to steer strategies and position sizing.

- MLEngine (online, lightweight): Incremental logistic regression with River for short-horizon regime classification from klines-derived features. Non-blocking I/O, model persistence with joblib, drift detection via ADWIN.
- HybridMLEngine (deep + online): LSTM/Transformer for long-horizon context combined with River-based short-horizon classifier. Exposes Prometheus metrics and integrates with `MarketRegime` and `RegimePrediction` types from `app/core/risk_manager.py`.

Key features
- Feature pipeline from klines: volatility, spread, volume, RSI, ATR
- Online training and drift handling (ADWIN)
- Async data access via `MarketDataCollector`
- Model save/load
- Regime predictions wired to strategy selection and risk controls

Dependencies
- Optional/online: River (`river`), `joblib`
- Deep: TensorFlow/Keras, scikit-learn (`StandardScaler`, `LabelEncoder`)
- Metrics: `prometheus_client`

Data model notes
- `app/services/ml_engine.RegimePrediction`: simple dataclass `{label: int, proba: float}` used internally by the lightweight engine.
- `app/core/risk_manager.RegimePrediction`: Pydantic model with fields `{long_regime, short_regime, long_conf, short_conf}` used across API/services. Hybrid engine returns this type.

Example: quick online prediction (MLEngine)
```python
import asyncio
from app.services.ml_engine import MLEngine

async def main():
    ml = MLEngine()
    pred = await ml.predict_regime(symbol="BTCUSDT", interval="1m", limit=60)
    print(pred.label, pred.proba)

    # Incremental train without blocking
    await ml.train_on_symbol("BTCUSDT", "1m", 60)
    await ml.save_model()

asyncio.run(main())
```

Example: hybrid prediction for strategy selection
```python
import asyncio
import pandas as pd
from app.services.hybrid_ml_engine import HybridMLEngine
from app.core.risk_manager import MarketRegime

async def main():
    engine = HybridMLEngine(models_dir="models")

    # Prepare/history window DataFrame must include columns like: close, volume, high, low,
    # and preferably technicals (rsi, macd, bb_upper/bb_lower, atr, volatility, returns)
    recent = pd.DataFrame({
        "close": [100, 101, 100.5, 102, 103],
        "volume": [1e6, 1.1e6, 1.05e6, 1.2e6, 1.15e6],
        "high": [101, 101.5, 101, 102.5, 103.5],
        "low": [99.5, 100.5, 100.2, 101.2, 102.3],
        "returns": [0, 0.01, -0.0049, 0.0149, 0.0098]
    })

    # Initialize short-horizon River model
    engine.initialize_river_model("BTCUSDT")
    features_now = {"volatility": 0.02, "spread": 0.001, "volume": 1_200_000, "rsi": 55.0, "atr": 1.2}

    # Predict combined regimes
    prediction = await engine.predict_regime(
        symbol="BTCUSDT",
        recent_data=recent,
        current_features=features_now,
    )
    # prediction is app.core.risk_manager.RegimePrediction
    print(prediction.long_regime, prediction.short_regime, prediction.long_conf, prediction.short_conf)

asyncio.run(main())
```

Operational guidance
- Use async flows for any I/O-bound operation (market data, DB, filesystem saves).
- When River is unavailable, `MLEngine` gracefully falls back and returns neutral predictions `(label=0, proba=0.5)`.
- Persist deep models with Hybrid engine to `models/` and record scaler and label encoder for reproducible inference.


