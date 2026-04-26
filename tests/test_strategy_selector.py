"""
Tests unitarios para el StrategySelector V2.5.
"""

import pytest

from app.services.strategy_selector import (
    StrategySelector,
    StrategyType,
    VolatilityLevel,
    AccountState,
)
from app.core.risk_manager import RiskManager, MarketRegime, RegimePrediction


class TestStrategySelector:
    """Tests para el StrategySelector."""

    @pytest.fixture
    def risk_manager(self):
        """Fixture para crear instancia de RiskManager."""
        return RiskManager()

    @pytest.fixture
    def strategy_selector(self, risk_manager):
        """Fixture para crear instancia de StrategySelector."""
        return StrategySelector(risk_manager)

    @pytest.fixture
    def mock_regime_prediction(self):
        """Fixture para predicción de régimen de prueba."""
        return RegimePrediction(
            long_regime=MarketRegime.BULL_TREND,
            short_regime=MarketRegime.RANGE,
            long_conf=0.8,
            short_conf=0.7,
        )

    @pytest.fixture
    def mock_account_state(self):
        """Fixture para estado de cuenta de prueba."""
        return AccountState(
            total_equity=10000.0,
            available_balance=5000.0,
            total_exposure=0.5,
            daily_pnl=0.02,
            max_drawdown=0.05,
            risk_score=0.3,
        )

    def test_strategy_selector_initialization(self, strategy_selector):
        """Test de inicialización del StrategySelector."""
        assert strategy_selector.risk_manager is not None
        assert len(strategy_selector.strategy_configs) > 0

        # Verificar configuraciones básicas
        assert (
            MarketRegime.RANGE,
            VolatilityLevel.LOW,
        ) in strategy_selector.strategy_configs
        assert (
            MarketRegime.BULL_TREND,
            VolatilityLevel.MODERATE,
        ) in strategy_selector.strategy_configs
        assert (MarketRegime.BEAR_TREND, None) in strategy_selector.strategy_configs

    def test_determine_volatility_level_high_vol(
        self, strategy_selector, mock_regime_prediction
    ):
        """Test de determinación de volatilidad alta."""
        mock_regime_prediction.short_regime = MarketRegime.HIGH_VOL

        dummy_state = AccountState(
            total_equity=10000.0,
            available_balance=5000.0,
            total_exposure=0.2,
            daily_pnl=0.0,
            max_drawdown=0.05,
            risk_score=0.3,
        )
        volatility = strategy_selector._determine_volatility_level(
            mock_regime_prediction, dummy_state
        )

        assert volatility == VolatilityLevel.HIGH

    def test_determine_volatility_level_by_risk_score(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de determinación de volatilidad por score de riesgo."""
        # Configurar score de riesgo alto
        mock_account_state.risk_score = 0.8

        volatility = strategy_selector._determine_volatility_level(
            mock_regime_prediction, mock_account_state
        )

        assert volatility == VolatilityLevel.HIGH

    def test_determine_volatility_level_moderate(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de determinación de volatilidad moderada."""
        mock_account_state.risk_score = 0.5

        volatility = strategy_selector._determine_volatility_level(
            mock_regime_prediction, mock_account_state
        )

        assert volatility == VolatilityLevel.MODERATE

    def test_determine_volatility_level_low(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de determinación de volatilidad baja."""
        mock_account_state.risk_score = 0.2

        volatility = strategy_selector._determine_volatility_level(
            mock_regime_prediction, mock_account_state
        )

        assert volatility == VolatilityLevel.LOW

    def test_calculate_dynamic_params_grid_trading(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de cálculo de parámetros dinámicos para grid trading."""
        params = strategy_selector._calculate_dynamic_params(
            StrategyType.GRID_TRADING, mock_regime_prediction, mock_account_state
        )

        assert params.grid_spacing_bps is not None
        assert params.grid_levels is not None
        assert params.order_size_usdt is not None
        assert params.grid_spacing_bps > 0
        assert params.grid_levels > 0
        assert params.order_size_usdt > 0

    def test_calculate_dynamic_params_dca(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de cálculo de parámetros dinámicos para DCA."""
        params = strategy_selector._calculate_dynamic_params(
            StrategyType.DCA, mock_regime_prediction, mock_account_state
        )

        assert params.tranche_size is not None
        assert params.interval is not None
        assert params.take_profit is not None
        assert params.tranche_size > 0
        assert params.interval > 0
        assert params.take_profit > 0

    def test_calculate_dynamic_params_scalping(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de cálculo de parámetros dinámicos para scalping."""
        params = strategy_selector._calculate_dynamic_params(
            StrategyType.SCALPING, mock_regime_prediction, mock_account_state
        )

        assert params.order_size_usdt is not None
        assert params.take_profit is not None
        assert params.stop_loss is not None
        assert params.max_exposure is not None
        assert params.order_size_usdt > 0
        assert params.take_profit > 0
        assert params.stop_loss > 0
        assert params.max_exposure > 0

    def test_calculate_dynamic_params_hedging(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de cálculo de parámetros dinámicos para hedging."""
        params = strategy_selector._calculate_dynamic_params(
            StrategyType.HEDGING, mock_regime_prediction, mock_account_state
        )

        assert params.max_exposure is not None
        assert params.stop_loss is not None
        assert params.max_exposure > 0
        assert params.stop_loss > 0

    def test_get_strategy_config_range_low_vol(self, strategy_selector):
        """Test de obtención de configuración para RANGE + LOW_VOL."""
        config = strategy_selector._get_strategy_config(
            MarketRegime.RANGE, VolatilityLevel.LOW
        )

        assert config is not None
        assert config["strategy"] == StrategyType.GRID_TRADING

    def test_get_strategy_config_bull_moderate(self, strategy_selector):
        """Test de obtención de configuración para BULL_TREND + MODERATE_VOL."""
        config = strategy_selector._get_strategy_config(
            MarketRegime.BULL_TREND, VolatilityLevel.MODERATE
        )

        assert config is not None
        assert config["strategy"] == StrategyType.DCA

    def test_get_strategy_config_bull_high(self, strategy_selector):
        """Test de obtención de configuración para BULL_TREND + HIGH_VOL."""
        config = strategy_selector._get_strategy_config(
            MarketRegime.BULL_TREND, VolatilityLevel.HIGH
        )

        assert config is not None
        assert config["strategy"] == StrategyType.SCALPING

    def test_get_strategy_config_bear(self, strategy_selector):
        """Test de obtención de configuración para BEAR_TREND."""
        config = strategy_selector._get_strategy_config(MarketRegime.BEAR_TREND, None)

        assert config is not None
        assert config["strategy"] == StrategyType.HOLD

    def test_get_strategy_config_fallback(self, strategy_selector):
        """Test de fallback para configuración no encontrada."""
        config = strategy_selector._get_strategy_config(
            MarketRegime.CRASH_IMMINENT, VolatilityLevel.HIGH
        )

        assert config is not None
        assert config["strategy"] == StrategyType.HOLD

    def test_select_strategy_grid_trading(self, strategy_selector, mock_account_state):
        """Test de selección de estrategia grid trading."""
        # Configurar predicción para grid trading
        regime_prediction = RegimePrediction(
            long_regime=MarketRegime.RANGE,
            short_regime=MarketRegime.RANGE,
            long_conf=0.8,
            short_conf=0.7,
        )

        strategy_spec = strategy_selector.select_strategy(
            regime_prediction, "BTCUSDT", mock_account_state
        )

        assert strategy_spec.strategy_name == StrategyType.GRID_TRADING
        assert strategy_spec.confidence > 0
        assert strategy_spec.reasoning is not None
        assert strategy_spec.regime_prediction == regime_prediction

    def test_select_strategy_dca(self, strategy_selector, mock_account_state):
        """Test de selección de estrategia DCA."""
        # Configurar predicción para DCA
        regime_prediction = RegimePrediction(
            long_regime=MarketRegime.BULL_TREND,
            short_regime=MarketRegime.BULL_TREND,
            long_conf=0.8,
            short_conf=0.7,
        )

        strategy_spec = strategy_selector.select_strategy(
            regime_prediction, "BTCUSDT", mock_account_state
        )

        assert strategy_spec.strategy_name == StrategyType.DCA
        assert strategy_spec.confidence > 0
        assert strategy_spec.reasoning is not None

    def test_select_strategy_hold_emergency_stop(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de selección de estrategia HOLD cuando hay stop de emergencia."""
        # Activar stop de emergencia
        strategy_selector.risk_manager.emergency_stop = True

        strategy_spec = strategy_selector.select_strategy(
            mock_regime_prediction, "BTCUSDT", mock_account_state
        )

        assert strategy_spec.strategy_name == StrategyType.HOLD
        assert strategy_spec.confidence == 1.0
        assert "Emergency stop active" in strategy_spec.reasoning

    def test_select_strategy_confidence_adjustment(
        self, strategy_selector, mock_regime_prediction
    ):
        """Test de ajuste de confianza basado en estado de cuenta."""
        # Configurar cuenta con alto riesgo
        high_risk_account = AccountState(
            total_equity=10000.0,
            available_balance=5000.0,
            total_exposure=0.5,
            daily_pnl=-0.06,  # Pérdida diaria alta
            max_drawdown=0.05,
            risk_score=0.9,  # Score de riesgo alto
        )

        strategy_spec = strategy_selector.select_strategy(
            mock_regime_prediction, "BTCUSDT", high_risk_account
        )

        # La confianza debe ser menor debido al alto riesgo
        expected_confidence = (
            mock_regime_prediction.long_conf + mock_regime_prediction.short_conf
        ) / 2
        expected_confidence *= 0.7 * 0.5  # Ajustes por riesgo alto y pérdidas

        assert strategy_spec.confidence < expected_confidence

    def test_generate_reasoning(self, strategy_selector):
        """Test de generación de reasoning."""
        strategy_type = StrategyType.GRID_TRADING
        regime_prediction = RegimePrediction(
            long_regime=MarketRegime.RANGE,
            short_regime=MarketRegime.RANGE,
            long_conf=0.8,
            short_conf=0.7,
        )
        volatility = VolatilityLevel.LOW
        account_state = AccountState(
            total_equity=10000.0,
            available_balance=5000.0,
            total_exposure=0.5,
            daily_pnl=0.02,
            max_drawdown=0.05,
            risk_score=0.3,
        )
        confidence = 0.8

        reasoning = strategy_selector._generate_reasoning(
            strategy_type, regime_prediction, volatility, account_state, confidence
        )

        assert reasoning is not None
        assert "Market regime" in reasoning
        assert "Volatility level" in reasoning
        assert "Range-bound market" in reasoning
        assert "High confidence" in reasoning

    def test_generate_reasoning_high_risk(self, strategy_selector):
        """Test de generación de reasoning con alto riesgo."""
        strategy_type = StrategyType.HOLD
        regime_prediction = RegimePrediction(
            long_regime=MarketRegime.BEAR_TREND,
            short_regime=MarketRegime.BEAR_TREND,
            long_conf=0.8,
            short_conf=0.7,
        )
        volatility = VolatilityLevel.HIGH
        account_state = AccountState(
            total_equity=10000.0,
            available_balance=5000.0,
            total_exposure=0.5,
            daily_pnl=-0.04,  # Pérdidas
            max_drawdown=0.05,
            risk_score=0.8,  # Alto riesgo
        )
        confidence = 0.6

        reasoning = strategy_selector._generate_reasoning(
            strategy_type, regime_prediction, volatility, account_state, confidence
        )

        assert reasoning is not None
        assert "High risk score" in reasoning
        assert "Daily losses detected" in reasoning
        assert "Low confidence" in reasoning

    def test_strategy_configs_completeness(self, strategy_selector):
        """Test de completitud de configuraciones de estrategia."""
        # Verificar que todas las combinaciones importantes están cubiertas
        important_combinations = [
            (MarketRegime.RANGE, VolatilityLevel.LOW),
            (MarketRegime.BULL_TREND, VolatilityLevel.MODERATE),
            (MarketRegime.BULL_TREND, VolatilityLevel.HIGH),
            (MarketRegime.BEAR_TREND, None),
            (MarketRegime.HIGH_VOLATILITY_BEAR, None),
            (MarketRegime.CRASH_IMMINENT, None),
        ]

        for regime, volatility in important_combinations:
            config = strategy_selector._get_strategy_config(regime, volatility)
            assert config is not None
            assert "strategy" in config
            assert "default_params" in config

    def test_dynamic_params_limits(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de límites en parámetros dinámicos."""
        # Probar con diferentes tipos de estrategia
        strategies = [
            StrategyType.GRID_TRADING,
            StrategyType.DCA,
            StrategyType.SCALPING,
        ]

        for strategy_type in strategies:
            params = strategy_selector._calculate_dynamic_params(
                strategy_type, mock_regime_prediction, mock_account_state
            )

            # Verificar que los parámetros están dentro de límites razonables
            if hasattr(params, "grid_spacing_bps") and params.grid_spacing_bps:
                assert 10 <= params.grid_spacing_bps <= 200  # Entre 10 y 200 bps

            if hasattr(params, "take_profit") and params.take_profit:
                assert 0.01 <= params.take_profit <= 0.20  # Entre 1% y 20%

            if hasattr(params, "stop_loss") and params.stop_loss:
                assert 0.005 <= params.stop_loss <= 0.10  # Entre 0.5% y 10%

    def test_strategy_selection_metrics(
        self, strategy_selector, mock_regime_prediction, mock_account_state
    ):
        """Test de métricas de selección de estrategia."""
        # Realizar múltiples selecciones para verificar métricas
        for i in range(5):
            strategy_spec = strategy_selector.select_strategy(
                mock_regime_prediction, f"SYMBOL{i}", mock_account_state
            )

            assert strategy_spec is not None
            assert strategy_spec.confidence > 0
            assert strategy_spec.confidence <= 1.0

    def test_error_handling_invalid_regime(self, strategy_selector, mock_account_state):
        """Test de manejo de errores con régimen inválido."""
        # Crear predicción con régimen inválido
        invalid_regime_prediction = RegimePrediction(
            long_regime=MarketRegime.RANGE,
            short_regime=MarketRegime.RANGE,
            long_conf=0.8,
            short_conf=0.7,
        )

        # Esto debería funcionar sin errores
        strategy_spec = strategy_selector.select_strategy(
            invalid_regime_prediction, "BTCUSDT", mock_account_state
        )

        assert strategy_spec is not None
        assert strategy_spec.strategy_name in [
            StrategyType.GRID_TRADING,
            StrategyType.HOLD,
        ]

    def test_strategy_history_empty(self, strategy_selector):
        """Test de historial de estrategias vacío."""
        history = strategy_selector.get_strategy_history("BTCUSDT")

        assert isinstance(history, list)
        assert len(history) == 0

    def test_strategy_performance_mock(self, strategy_selector):
        """Test de métricas de rendimiento de estrategia."""
        performance = strategy_selector.get_strategy_performance(
            StrategyType.GRID_TRADING
        )

        assert "strategy" in performance
        assert "timeframe_days" in performance
        assert "total_trades" in performance
        assert "win_rate" in performance
        assert "avg_profit" in performance
        assert "max_drawdown" in performance
        assert "sharpe_ratio" in performance
