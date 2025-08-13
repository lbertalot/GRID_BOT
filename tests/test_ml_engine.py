import os
import sys
import pytest
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ml_engine import MLEngine


@pytest.mark.asyncio
async def test_ml_engine_predict_and_train():
    ml = MLEngine()
    # Debe predecir aunque river no esté disponible (fallback)
    pred = await ml.predict_regime("BTCUSDT", "1m", 10)
    assert pred.label in (0, 1)
    assert 0.0 <= pred.proba <= 1.0
    # Entrenamiento no debe romper
    await ml.train_on_symbol("BTCUSDT", "1m", 10)


