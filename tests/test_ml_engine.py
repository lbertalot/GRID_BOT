import os
import sys
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ml_engine import (
    MLEngine,
    RegimePrediction as MLRegimePrediction,
    ml_prediction_to_regime_prediction,
)
from app.core.risk_manager import MarketRegime


def test_ml_prediction_to_regime_prediction_label_zero():
    """label=0 -> RANGE, confianza = proba."""
    rp = ml_prediction_to_regime_prediction(MLRegimePrediction(label=0, proba=0.3))
    assert rp.long_regime == MarketRegime.RANGE
    assert rp.short_regime == MarketRegime.RANGE
    assert rp.long_conf == 0.3
    assert rp.short_conf == 0.3


def test_ml_prediction_to_regime_prediction_label_one():
    """label=1 -> BULL_TREND."""
    rp = ml_prediction_to_regime_prediction(MLRegimePrediction(label=1, proba=0.85))
    assert rp.long_regime == MarketRegime.BULL_TREND
    assert rp.short_regime == MarketRegime.BULL_TREND
    assert rp.long_conf == 0.85
    assert rp.short_conf == 0.85


def test_ml_prediction_to_regime_prediction_clamps_confidence():
    """proba fuera de [0,1] se trunca."""
    rp = ml_prediction_to_regime_prediction(MLRegimePrediction(label=0, proba=1.5))
    assert rp.long_conf == 1.0
    assert rp.short_conf == 1.0


@pytest.mark.asyncio
async def test_ml_engine_predict_and_train():
    ml = MLEngine()
    # Debe predecir aunque river no esté disponible (fallback)
    pred = await ml.predict_regime("BTCUSDT", "1m", 10)
    assert pred.label in (0, 1)
    assert 0.0 <= pred.proba <= 1.0
    # Entrenamiento no debe romper
    await ml.train_on_symbol("BTCUSDT", "1m", 10)
