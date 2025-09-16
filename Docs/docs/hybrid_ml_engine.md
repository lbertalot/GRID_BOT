### HybridMLEngine (Deep + Online)

Location: `app/services/hybrid_ml_engine.py`

Purpose
- Combine deep learning (LSTM/Transformer) for long-horizon context with River online models for short-horizon classification.
- Emit Prometheus metrics for observability.
- Return `app.core.risk_manager.RegimePrediction` for system-wide compatibility.

Configs
- `ModelConfig`: common hyperparameters (sequence_length, hidden_units, dropout_rate, learning_rate, batch_size, epochs, validation_split)
- `DeepModelConfig(ModelConfig)`: `model_type` in {"LSTM", "Transformer"}, `num_layers`, `attention_heads`
- `RiverModelConfig`: `model_type` in {"HoeffdingTree", "AdaptiveRandomForest", "LogisticRegression"}, plus hyperparameters

Core methods
- `async train_deep_model(history_df: pd.DataFrame, symbol: str, output_path: Optional[str] = None, config: Optional[DeepModelConfig] = None) -> str`
  - Prepares features, creates model (LSTM or Transformer), trains with early stopping/LR scheduling, saves `model.h5`, `scaler.pkl`, `label_encoder.pkl`, and `config.json`. Records metrics (accuracy, duration).
- `load_deep_model(path: str, symbol: str) -> bool`
  - Loads model, scaler, label encoder, and config into memory for `symbol`.
- `initialize_river_model(symbol: str) -> None`
  - Instantiates online model and accuracy metric for `symbol`.
- `update_river_model(symbol: str, features: Dict[str, float], regime: MarketRegime) -> None`
  - Learns one sample and updates accuracy; call in streaming loops where ground truth is available.
- `predict_long_regime(symbol: str, recent_window: pd.DataFrame) -> Tuple[MarketRegime, float]`
  - Runs deep model on the latest sequence, returns predicted regime and confidence.
- `predict_short_regime(symbol: str, features: Dict[str, float]) -> Tuple[MarketRegime, float]`
  - Uses River model for current snapshot features; returns regime with heuristic confidence.
- `async predict_regime(symbol: str, recent_data: pd.DataFrame, current_features: Dict[str, float]) -> RegimePrediction`
  - Combines long/short predictions into a single Pydantic `RegimePrediction`.
- `get_model_status(symbol: str) -> Dict[str, Any]`
  - Returns whether models are loaded/initialized, last prediction, and metrics snapshots.

Expected columns for deep window
- Prefer: `close, volume, high, low, rsi, macd, bb_upper, bb_lower, atr, volatility, returns`
- Minimal fallback: `close, volume, high, low`

Metrics
- `regime_predictions_total{symbol,long,short}`
- `regime_confidence{symbol,horizon}`
- `model_training_duration_seconds{model_type,symbol}`
- `model_accuracy{model_type,symbol}`

Usage example
```python
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from app.services.hybrid_ml_engine import HybridMLEngine, DeepModelConfig

async def main():
    engine = HybridMLEngine(models_dir="models")

    # Assume you have a historical DataFrame `hist_df` with the required columns
    # Train deep model once (offline or scheduled)
    # path = await engine.train_deep_model(hist_df, symbol="ETHUSDT", config=DeepModelConfig(model_type="LSTM", epochs=20))
    # engine.load_deep_model(path, symbol="ETHUSDT")

    # Prepare a recent window and current features
    recent = pd.DataFrame({"close": [100, 101, 102, 103, 104], "volume": [1,2,3,4,5], "high": [101,102,103,104,105], "low": [99,100,101,102,103], "returns": [0, .01, .0099, .0098, .0097]})
    current_features = {"volatility": 0.015, "spread": 0.001, "volume": 1_500_000, "rsi": 58.0, "atr": 0.9}

    # Initialize (if needed) and predict
    engine.initialize_river_model("ETHUSDT")
    pred = await engine.predict_regime("ETHUSDT", recent, current_features)
    print(pred.dict())

asyncio.run(main())
```

Operational tips
- Set a fixed random seed for TF (`tf.random.set_seed(42)`) for reproducibility.
- Store models under `models/{symbol}_deep_{type}_{timestamp}/` to version artifacts alongside scalers and encoders.
- Use the River side online in production to adapt between deep retrains.