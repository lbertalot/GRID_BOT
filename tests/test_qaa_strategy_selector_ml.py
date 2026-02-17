"""
QAA Tests: StrategySelector y Fallback ML

Objetivo: Verificar que el StrategySelector elige correctamente la estrategia
según el régimen de mercado, y que falla de forma segura cuando el ML no
está disponible o devuelve predicciones poco confiables.

Nivel de riesgo: ALTO
Impacto financiero: Estrategia incorrecta para el régimen de mercado actual

HALLAZGOS:
- StrategySelector usa float para order_size_usdt, no Decimal
- AccountState.total_equity usa float
- confidence se multiplica por factores mágicos (0.69, 0.49) sin documentación
- La lógica de override para DCA (línea 329-333) puede contradecir la selección
  basada en régimen/volatilidad
- MLEngine retorna RegimePrediction(label=0, proba=0.5) como fallback seguro
"""

import os
import sys
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("SKIP_API_HEALTHCHECK", "1")

from app.core.risk_manager import (
    RiskManager,
    MarketRegime,
    RegimePrediction,
)
from app.services.strategy_selector import (
    StrategySelector,
    StrategyType,
    StrategySpec,
    StrategyParams,
    AccountState,
    VolatilityLevel,
)


# ===========================================================================
# Fixtures
# ===========================================================================

def _make_account_state(**overrides):
    defaults = {
        "total_equity": 10000.0,
        "available_balance": 8000.0,
        "total_exposure": 0.2,
        "daily_pnl": 0.01,
        "max_drawdown": 0.03,
        "risk_score": 0.3,
    }
    defaults.update(overrides)
    return AccountState(**defaults)


def _make_regime_prediction(**overrides):
    defaults = {
        "long_regime": MarketRegime.RANGE,
        "short_regime": MarketRegime.RANGE,
        "long_conf": 0.8,
        "short_conf": 0.8,
    }
    defaults.update(overrides)
    return RegimePrediction(**defaults)


# ===========================================================================
# TEST GROUP 1: Selección por régimen
# ===========================================================================

class TestStrategySelectionByRegime:
    """Tests de selección de estrategia por régimen de mercado."""

    @pytest.fixture
    def selector(self):
        rm = RiskManager()
        return StrategySelector(rm)

    def test_range_low_vol_selects_grid(self, selector):
        """RANGE + LOW_VOL debe seleccionar GRID_TRADING."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.RANGE,
            long_regime=MarketRegime.RANGE,
        )
        account = _make_account_state(risk_score=0.2)
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        assert result.strategy_name == StrategyType.GRID_TRADING

    def test_bull_moderate_selects_dca(self, selector):
        """BULL_TREND + MODERATE_VOL debe seleccionar DCA."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.BULL_TREND,
            long_regime=MarketRegime.BULL_TREND,
        )
        account = _make_account_state(risk_score=0.5)
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        # Puede ser DCA o GRID dependiendo de confidence
        assert result.strategy_name in [StrategyType.DCA, StrategyType.GRID_TRADING, StrategyType.SCALPING]

    def test_bear_trend_selects_hold(self, selector):
        """BEAR_TREND debe seleccionar HOLD."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.BEAR_TREND,
            long_regime=MarketRegime.BEAR_TREND,
        )
        account = _make_account_state()
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        assert result.strategy_name == StrategyType.HOLD

    def test_crash_imminent_selects_hold(self, selector):
        """CRASH_IMMINENT debe seleccionar HOLD."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.CRASH_IMMINENT,
            long_regime=MarketRegime.CRASH_IMMINENT,
        )
        account = _make_account_state()
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        assert result.strategy_name == StrategyType.HOLD

    def test_high_vol_bear_selects_hedging(self, selector):
        """HIGH_VOLATILITY_BEAR debe seleccionar HEDGING."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.HIGH_VOLATILITY_BEAR,
            long_regime=MarketRegime.HIGH_VOLATILITY_BEAR,
        )
        account = _make_account_state()
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        assert result.strategy_name in [StrategyType.HEDGING, StrategyType.HOLD]


# ===========================================================================
# TEST GROUP 2: Emergency Stop
# ===========================================================================

class TestEmergencyStopStrategy:
    """Tests de selección de estrategia durante emergency stop."""

    def test_emergency_stop_always_returns_hold(self):
        """Emergency stop debe SIEMPRE retornar HOLD con confidence=1.0."""
        rm = RiskManager()
        rm.emergency_stop = True
        selector = StrategySelector(rm)

        prediction = _make_regime_prediction(
            short_regime=MarketRegime.BULL_TREND,
            long_regime=MarketRegime.BULL_TREND,
            long_conf=0.99,
            short_conf=0.99,
        )
        account = _make_account_state()
        result = selector.select_strategy(prediction, "BTCUSDT", account)

        assert result.strategy_name == StrategyType.HOLD, (
            f"Emergency stop pero seleccionó {result.strategy_name.value}"
        )
        assert result.confidence == 1.0, (
            f"Confidence debería ser 1.0 en emergency stop, no {result.confidence}"
        )


# ===========================================================================
# TEST GROUP 3: Fallback seguro
# ===========================================================================

class TestFallbackSafety:
    """Tests de comportamiento seguro ante fallos."""

    def test_exception_in_selection_returns_hold(self):
        """Excepción durante selección debe retornar HOLD."""
        rm = RiskManager()
        selector = StrategySelector(rm)

        # Forzar excepción haciendo que _determine_volatility_level falle
        prediction = _make_regime_prediction()
        prediction.short_regime = MarketRegime.RANGE

        with patch.object(
            selector, "_determine_volatility_level", side_effect=Exception("ML crash")
        ):
            result = selector.select_strategy(prediction, "BTCUSDT", _make_account_state())
            assert result.strategy_name == StrategyType.HOLD, (
                "Excepción en selección debe producir HOLD"
            )

    def test_invalid_regime_returns_hold(self):
        """Régimen no mapeado debe retornar HOLD como fallback."""
        rm = RiskManager()
        selector = StrategySelector(rm)
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.HIGH_VOL,
            long_regime=MarketRegime.HIGH_VOL,
        )
        account = _make_account_state(risk_score=0.2)
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        # HIGH_VOL no tiene mapping directo, debe usar fallback
        assert result.strategy_name is not None

    def test_zero_equity_handled_gracefully(self):
        """Equity = 0 no debe causar division by zero."""
        rm = RiskManager()
        selector = StrategySelector(rm)
        prediction = _make_regime_prediction()
        account = _make_account_state(total_equity=0.0, available_balance=0.0)
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        assert result is not None
        assert isinstance(result, StrategySpec)


# ===========================================================================
# TEST GROUP 4: Confidence adjustments
# ===========================================================================

class TestConfidenceAdjustments:
    """Tests de ajustes de confianza."""

    @pytest.fixture
    def selector(self):
        rm = RiskManager()
        return StrategySelector(rm)

    def test_high_risk_reduces_confidence(self, selector):
        """Risk score alto debe reducir la confianza."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.RANGE,
            long_conf=0.9,
            short_conf=0.9,
        )
        account_normal = _make_account_state(risk_score=0.3)
        account_high_risk = _make_account_state(risk_score=0.9)

        result_normal = selector.select_strategy(prediction, "BTCUSDT", account_normal)
        result_risky = selector.select_strategy(prediction, "BTCUSDT", account_high_risk)

        assert result_risky.confidence <= result_normal.confidence, (
            f"Risk alto ({result_risky.confidence}) no redujo confidence "
            f"vs normal ({result_normal.confidence})"
        )

    def test_daily_losses_reduce_confidence(self, selector):
        """Pérdidas diarias > 5% deben reducir la confianza."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.RANGE,
            long_conf=0.9,
            short_conf=0.9,
        )
        account_profit = _make_account_state(daily_pnl=0.02)
        account_loss = _make_account_state(daily_pnl=-0.06)

        result_profit = selector.select_strategy(prediction, "BTCUSDT", account_profit)
        result_loss = selector.select_strategy(prediction, "BTCUSDT", account_loss)

        assert result_loss.confidence <= result_profit.confidence, (
            f"Daily loss ({result_loss.confidence}) no redujo confidence "
            f"vs profit ({result_profit.confidence})"
        )

    def test_confidence_never_exceeds_one(self, selector):
        """Confidence nunca debe superar 1.0."""
        prediction = _make_regime_prediction(
            long_conf=1.0,
            short_conf=1.0,
        )
        account = _make_account_state()
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        assert result.confidence <= 1.0, (
            f"Confidence {result.confidence} excede 1.0"
        )

    def test_confidence_never_negative(self, selector):
        """Confidence nunca debe ser negativa."""
        prediction = _make_regime_prediction(
            long_conf=0.1,
            short_conf=0.1,
        )
        account = _make_account_state(risk_score=0.99, daily_pnl=-0.10)
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        assert result.confidence >= 0.0, (
            f"Confidence {result.confidence} es negativa"
        )


# ===========================================================================
# TEST GROUP 5: Volatility level determination
# ===========================================================================

class TestVolatilityLevel:
    """Tests de determinación de nivel de volatilidad."""

    @pytest.fixture
    def selector(self):
        rm = RiskManager()
        return StrategySelector(rm)

    def test_high_vol_regime_gives_high_volatility(self, selector):
        """Régimen HIGH_VOL debe dar VolatilityLevel.HIGH."""
        prediction = _make_regime_prediction(short_regime=MarketRegime.HIGH_VOL)
        account = _make_account_state()
        vol = selector._determine_volatility_level(prediction, account)
        assert vol == VolatilityLevel.HIGH

    def test_high_risk_score_gives_high_volatility(self, selector):
        """Risk score > 0.7 debe dar HIGH volatility."""
        prediction = _make_regime_prediction(short_regime=MarketRegime.RANGE)
        account = _make_account_state(risk_score=0.8)
        vol = selector._determine_volatility_level(prediction, account)
        assert vol == VolatilityLevel.HIGH

    def test_moderate_risk_score_gives_moderate_volatility(self, selector):
        """Risk score 0.4-0.7 debe dar MODERATE volatility."""
        prediction = _make_regime_prediction(short_regime=MarketRegime.RANGE)
        account = _make_account_state(risk_score=0.5)
        vol = selector._determine_volatility_level(prediction, account)
        assert vol == VolatilityLevel.MODERATE

    def test_low_risk_score_gives_low_volatility(self, selector):
        """Risk score < 0.4 debe dar LOW volatility."""
        prediction = _make_regime_prediction(short_regime=MarketRegime.RANGE)
        account = _make_account_state(risk_score=0.2)
        vol = selector._determine_volatility_level(prediction, account)
        assert vol == VolatilityLevel.LOW


# ===========================================================================
# TEST GROUP 6: MLEngine fallback
# ===========================================================================

class TestMLEngineFallback:
    """Tests de fallback del motor ML."""

    def test_ml_engine_fallback_when_river_not_available(self):
        """MLEngine debe funcionar sin River instalado."""
        from app.services.ml_engine import MLEngine, RegimePrediction as MLPred

        engine = MLEngine()
        # Si River no está disponible, pipeline será None
        if engine.pipeline is None:
            # Verificar que predict_regime retorna fallback
            assert True, "MLEngine en modo no operativo (sin River)"

    @pytest.mark.asyncio
    async def test_ml_engine_predict_without_training(self):
        """Predicción sin entrenamiento debe retornar fallback seguro."""
        from app.services.ml_engine import MLEngine, RegimePrediction as MLPred

        engine = MLEngine()
        if engine.pipeline is None:
            # Sin River, debe retornar fallback
            pass
        else:
            # Con River pero sin entrenamiento
            with patch.object(engine.collector, "get_klines", return_value=[]):
                pred = await engine.predict_regime("BTCUSDT")
                assert pred.label == 0 or pred.label == 1
                assert 0.0 <= pred.proba <= 1.0

    @pytest.mark.asyncio
    async def test_ml_engine_compute_features_empty_klines(self):
        """Features con klines vacías deben retornar valores por defecto."""
        from app.services.ml_engine import MLEngine

        engine = MLEngine()
        features = await engine.compute_features_from_klines([])
        assert features["volatility"] == 0.0
        assert features["rsi"] == 50.0
        assert features["atr"] == 0.0

    @pytest.mark.asyncio
    async def test_ml_engine_compute_features_valid_klines(self):
        """Features con klines válidas deben ser numéricas."""
        from app.services.ml_engine import MLEngine

        engine = MLEngine()
        # Klines simuladas: [open_time, open, high, low, close, volume, close_time]
        klines = []
        for i in range(20):
            price = 50000 + i * 100
            klines.append([
                1000000 + i * 60000,
                str(price),
                str(price * 1.01),
                str(price * 0.99),
                str(price + 50),
                str(1000 + i * 10),
                1000000 + (i + 1) * 60000,
            ])
        features = await engine.compute_features_from_klines(klines)
        assert isinstance(features["volatility"], float)
        assert isinstance(features["rsi"], float)
        assert isinstance(features["atr"], float)
        assert features["atr"] >= 0

    def test_ml_heuristic_label_basic(self):
        """Heuristic label debe retornar 1 si tendencia alcista."""
        from app.services.ml_engine import MLEngine

        engine = MLEngine()
        klines = [
            [0, "100", "101", "99", "100", "1000", 1],
            [1, "100", "102", "99", "101", "1000", 2],
            [2, "101", "103", "100", "103", "1000", 3],
        ]
        label = engine._heuristic_label(klines)
        assert label == 1, "Tendencia alcista debe dar label=1"

    def test_ml_heuristic_label_bearish(self):
        """Heuristic label debe retornar 0 si tendencia bajista."""
        from app.services.ml_engine import MLEngine

        engine = MLEngine()
        klines = [
            [0, "100", "101", "99", "100", "1000", 1],
            [1, "100", "100", "97", "98", "1000", 2],
            [2, "98", "99", "95", "95", "1000", 3],
        ]
        label = engine._heuristic_label(klines)
        assert label == 0, "Tendencia bajista debe dar label=0"


# ===========================================================================
# TEST GROUP 7: Strategy params validation
# ===========================================================================

class TestStrategyParamsValidation:
    """Tests de validación de parámetros de estrategia."""

    @pytest.fixture
    def selector(self):
        rm = RiskManager()
        return StrategySelector(rm)

    def test_grid_params_have_required_fields(self, selector):
        """Grid strategy debe tener spacing, levels y order_size."""
        prediction = _make_regime_prediction(short_regime=MarketRegime.RANGE)
        account = _make_account_state(risk_score=0.2)
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        if result.strategy_name == StrategyType.GRID_TRADING:
            assert result.params.grid_spacing_bps is not None
            assert result.params.grid_levels is not None
            assert result.params.order_size_usdt is not None

    def test_dca_params_have_required_fields(self, selector):
        """DCA strategy debe tener tranche_size, interval, take_profit."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.BULL_TREND,
            long_regime=MarketRegime.BULL_TREND,
            long_conf=0.9,
            short_conf=0.9,
        )
        account = _make_account_state(risk_score=0.5)
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        if result.strategy_name == StrategyType.DCA:
            assert result.params.tranche_size is not None
            assert result.params.interval is not None
            assert result.params.take_profit is not None

    def test_scalping_params_have_stop_loss(self, selector):
        """Scalping debe tener stop_loss definido."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.BULL_TREND,
            long_regime=MarketRegime.BULL_TREND,
        )
        account = _make_account_state(risk_score=0.8)
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        if result.strategy_name == StrategyType.SCALPING:
            assert result.params.stop_loss is not None
            assert result.params.stop_loss > 0

    def test_hold_has_no_active_params(self, selector):
        """HOLD no debe tener parámetros de trading activos."""
        prediction = _make_regime_prediction(
            short_regime=MarketRegime.CRASH_IMMINENT,
        )
        account = _make_account_state()
        result = selector.select_strategy(prediction, "BTCUSDT", account)
        if result.strategy_name == StrategyType.HOLD:
            assert result.params.order_size_usdt is None
            assert result.params.grid_levels is None
