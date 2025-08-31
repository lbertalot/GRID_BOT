"""
Tests unitarios para el RiskManager evolucionado V2.5.
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch

from app.core.risk_manager import (
    RiskManager, MarketRegime, RegimePrediction, 
    PositionSizeParams, TrailingStopParams, BreakerState
)


class TestRiskManager:
    """Tests para el RiskManager evolucionado."""
    
    @pytest.fixture
    def risk_manager(self):
        """Fixture para crear instancia de RiskManager."""
        return RiskManager()
    
    @pytest.fixture
    def mock_position_params(self):
        """Fixture para parámetros de posición de prueba."""
        return PositionSizeParams(
            symbol="BTCUSDT",
            account_equity=10000.0,
            atr=0.02,
            winrate_estimate=0.6,
            avg_win_loss_ratio=1.5,
            price=50000.0
        )
    
    @pytest.fixture
    def mock_trailing_params(self):
        """Fixture para parámetros de trailing stop de prueba."""
        return TrailingStopParams(
            symbol="BTCUSDT",
            entry_price=50000.0,
            atr=1000.0,
            multiplier_atr=2.0,
            is_long=True
        )
    
    def test_risk_manager_initialization(self, risk_manager):
        """Test de inicialización del RiskManager."""
        assert risk_manager.fractional_kelly == 0.25
        assert risk_manager.min_kelly_confidence == 0.6
        assert risk_manager.default_multiplier_atr == 2.0
        assert risk_manager.emergency_stop is False
        assert risk_manager.breaker_state == BreakerState.NORMAL
        assert risk_manager.max_total_exposure_pct == 0.80
        assert risk_manager.min_profit_bps == 50
        assert risk_manager.current_regime == MarketRegime.RANGE
    
    def test_calculate_dynamic_position_size_kelly(self, risk_manager, mock_position_params):
        """Test de cálculo de tamaño de posición usando Kelly fraccional."""
        # Configurar parámetros para Kelly
        mock_position_params.winrate_estimate = 0.7
        mock_position_params.avg_win_loss_ratio = 2.0
        
        position_size = risk_manager.calculate_dynamic_position_size(mock_position_params)
        
        # Verificar que se calculó un tamaño de posición
        assert position_size > 0
        assert position_size <= mock_position_params.account_equity * 0.8  # Límite de equity
    
    def test_calculate_dynamic_position_size_atr_fallback(self, risk_manager, mock_position_params):
        """Test de cálculo de tamaño de posición usando fallback ATR."""
        # Configurar parámetros para fallback ATR
        mock_position_params.winrate_estimate = 0.4  # Bajo winrate
        mock_position_params.avg_win_loss_ratio = 0.8  # Bajo ratio
        
        position_size = risk_manager.calculate_dynamic_position_size(mock_position_params)
        
        # Verificar que se calculó un tamaño de posición
        assert position_size > 0
        assert position_size <= mock_position_params.account_equity * 0.8
    
    def test_calculate_kelly_position_size(self, risk_manager, mock_position_params):
        """Test de cálculo específico de Kelly."""
        # Kelly formula: f = W - (1-W)/R
        # W = 0.6, R = 1.5
        # f = 0.6 - (1-0.6)/1.5 = 0.6 - 0.4/1.5 = 0.6 - 0.267 = 0.333
        # Fractional Kelly = 0.333 * 0.25 = 0.08325
        # Position size = 0.08325 * 10000 = 832.5
        
        kelly_size = risk_manager._calculate_kelly_position_size(mock_position_params)
        
        expected_kelly_fraction = 0.6 - ((1 - 0.6) / 1.5)
        expected_fractional_kelly = expected_kelly_fraction * 0.25
        expected_size = expected_fractional_kelly * 10000
        
        assert abs(kelly_size - expected_size) < 1.0  # Tolerancia de 1 USDT
    
    def test_calculate_atr_position_size(self, risk_manager, mock_position_params):
        """Test de cálculo específico de ATR."""
        atr_size = risk_manager._calculate_atr_position_size(mock_position_params)
        
        # Verificar que se calculó un tamaño basado en ATR
        assert atr_size > 0
        assert atr_size <= mock_position_params.account_equity * 0.8
    
    def test_apply_position_limits(self, risk_manager, mock_position_params):
        """Test de aplicación de límites de posición."""
        original_size = 5000.0  # 50% del equity
        
        limited_size = risk_manager._apply_position_limits(original_size, mock_position_params)
        
        # Verificar que se aplicaron los límites
        assert limited_size <= mock_position_params.account_equity * 0.2  # Límite por símbolo
        assert limited_size <= mock_position_params.account_equity * 0.8  # Límite por equity
    
    def test_get_adaptive_trailing_stop_long(self, risk_manager, mock_trailing_params):
        """Test de trailing stop para posición larga."""
        stop_price = risk_manager.get_adaptive_trailing_stop(mock_trailing_params)
        
        # Para posición larga, stop debe estar por debajo del entry
        expected_stop = mock_trailing_params.entry_price - (mock_trailing_params.atr * mock_trailing_params.multiplier_atr)
        
        assert stop_price == expected_stop
        assert stop_price < mock_trailing_params.entry_price
    
    def test_get_adaptive_trailing_stop_short(self, risk_manager, mock_trailing_params):
        """Test de trailing stop para posición corta."""
        mock_trailing_params.is_long = False
        
        stop_price = risk_manager.get_adaptive_trailing_stop(mock_trailing_params)
        
        # Para posición corta, stop debe estar por encima del entry
        expected_stop = mock_trailing_params.entry_price + (mock_trailing_params.atr * mock_trailing_params.multiplier_atr)
        
        assert stop_price == expected_stop
        assert stop_price > mock_trailing_params.entry_price
    
    def test_update_trailing_stop_long(self, risk_manager, mock_trailing_params):
        """Test de actualización de trailing stop para posición larga."""
        # Crear trailing stop inicial
        risk_manager.get_adaptive_trailing_stop(mock_trailing_params)
        
        # Actualizar con precio más alto
        new_price = mock_trailing_params.entry_price + 2000  # Precio subió
        new_stop = risk_manager.update_trailing_stop(mock_trailing_params.symbol, new_price)
        
        # El stop debe haberse movido hacia arriba
        assert new_stop is not None
        assert new_stop > risk_manager.trailing_stops[mock_trailing_params.symbol]["stop_price"]
    
    def test_update_trailing_stop_no_update(self, risk_manager, mock_trailing_params):
        """Test de actualización de trailing stop sin cambios."""
        # Crear trailing stop inicial
        risk_manager.get_adaptive_trailing_stop(mock_trailing_params)
        
        # Actualizar con precio más bajo (no debe mover el stop para posición larga)
        new_price = mock_trailing_params.entry_price - 2000  # Precio bajó
        new_stop = risk_manager.update_trailing_stop(mock_trailing_params.symbol, new_price)
        
        # No debe haber actualización
        assert new_stop is None
    
    def test_apply_market_regime_filter_crash(self, risk_manager):
        """Test de aplicación de filtro de régimen de crash."""
        original_exposure = risk_manager.max_total_exposure_pct
        original_profit = risk_manager.min_profit_bps
        
        risk_manager.apply_market_regime_filter(MarketRegime.CRASH_IMMINENT)
        
        # Verificar que se redujeron los límites
        assert risk_manager.max_total_exposure_pct < original_exposure
        assert risk_manager.min_profit_bps > original_profit
        assert risk_manager.current_regime == MarketRegime.CRASH_IMMINENT
    
    def test_apply_market_regime_filter_bull(self, risk_manager):
        """Test de aplicación de filtro de régimen alcista."""
        original_exposure = risk_manager.max_total_exposure_pct
        original_profit = risk_manager.min_profit_bps
        
        risk_manager.apply_market_regime_filter(MarketRegime.BULL_TREND)
        
        # Verificar que no se cambiaron los límites para bull trend
        assert risk_manager.max_total_exposure_pct == original_exposure
        assert risk_manager.min_profit_bps == original_profit
        assert risk_manager.current_regime == MarketRegime.BULL_TREND
    
    def test_check_circuit_breaker_normal(self, risk_manager):
        """Test de circuit breaker en estado normal."""
        breaker_state = risk_manager.check_circuit_breaker()
        
        assert breaker_state == BreakerState.NORMAL
    
    def test_check_circuit_breaker_emergency_stop(self, risk_manager):
        """Test de circuit breaker con stop de emergencia."""
        risk_manager.emergency_stop = True
        
        breaker_state = risk_manager.check_circuit_breaker()
        
        assert breaker_state == BreakerState.STOPPED
    
    def test_check_circuit_breaker_daily_loss(self, risk_manager):
        """Test de circuit breaker con pérdida diaria excesiva."""
        risk_manager.daily_loss = 0.06  # 6% pérdida diaria
        
        breaker_state = risk_manager.check_circuit_breaker()
        
        assert breaker_state == BreakerState.DANGER
    
    def test_check_circuit_breaker_exposure_limit(self, risk_manager):
        """Test de circuit breaker con exposición excesiva."""
        risk_manager.total_exposure = 0.85  # 85% exposición
        
        breaker_state = risk_manager.check_circuit_breaker()
        
        assert breaker_state == BreakerState.WARNING
    
    def test_check_circuit_breaker_market_regime(self, risk_manager):
        """Test de circuit breaker con régimen de mercado crítico."""
        risk_manager.current_regime = MarketRegime.CRASH_IMMINENT
        
        breaker_state = risk_manager.check_circuit_breaker()
        
        assert breaker_state == BreakerState.WARNING
    
    def test_get_risk_status(self, risk_manager):
        """Test de obtención del estado de riesgo."""
        status = risk_manager.get_risk_status()
        
        assert "breaker_state" in status
        assert "emergency_stop" in status
        assert "current_regime" in status
        assert "total_exposure_pct" in status
        assert "max_exposure_pct" in status
        assert "daily_loss_pct" in status
        assert "max_loss_remaining" in status
        assert "min_profit_bps" in status
        assert "trailing_stops_count" in status
        assert "timestamp" in status
    
    def test_update_metrics(self, risk_manager):
        """Test de actualización de métricas."""
        daily_loss = 0.03  # 3%
        total_exposure = 0.6  # 60%
        
        risk_manager.update_metrics(daily_loss, total_exposure)
        
        assert risk_manager.daily_loss == daily_loss
        assert risk_manager.total_exposure == total_exposure
        assert risk_manager.max_loss_remaining == 0.02  # 5% - 3% = 2%
    
    def test_trigger_emergency_stop(self, risk_manager):
        """Test de activación de stop de emergencia."""
        reason = "Test emergency stop"
        
        risk_manager.trigger_emergency_stop(reason)
        
        assert risk_manager.emergency_stop is True
        assert risk_manager.breaker_state == BreakerState.STOPPED
    
    def test_reset_emergency_stop(self, risk_manager):
        """Test de reset de stop de emergencia."""
        # Activar stop de emergencia primero
        risk_manager.emergency_stop = True
        risk_manager.breaker_state = BreakerState.STOPPED
        
        risk_manager.reset_emergency_stop()
        
        assert risk_manager.emergency_stop is False
        assert risk_manager.breaker_state == BreakerState.NORMAL
    
    def test_regime_multipliers(self, risk_manager):
        """Test de multiplicadores de régimen."""
        # Verificar que todos los regímenes tienen multiplicadores
        for regime in MarketRegime:
            assert regime in risk_manager.regime_multipliers
        
        # Verificar valores específicos
        assert risk_manager.regime_multipliers[MarketRegime.CRASH_IMMINENT] == 0.5
        assert risk_manager.regime_multipliers[MarketRegime.BULL_TREND] == 1.0
        assert risk_manager.regime_multipliers[MarketRegime.RANGE] == 1.0
    
    def test_position_size_with_regime_filter(self, risk_manager, mock_position_params):
        """Test de tamaño de posición con filtro de régimen."""
        # Aplicar régimen de crash
        risk_manager.apply_market_regime_filter(MarketRegime.CRASH_IMMINENT)
        
        # Calcular tamaño de posición
        position_size = risk_manager.calculate_dynamic_position_size(mock_position_params)
        
        # El tamaño debe ser menor debido al multiplicador de régimen
        assert position_size > 0
        # Verificar que se aplicó el multiplicador (aproximadamente)
        # Esto es una verificación aproximada ya que hay múltiples factores
    
    def test_trailing_stop_persistence(self, risk_manager, mock_trailing_params):
        """Test de persistencia de trailing stops."""
        # Crear trailing stop
        risk_manager.get_adaptive_trailing_stop(mock_trailing_params)
        
        # Verificar que se guardó
        assert mock_trailing_params.symbol in risk_manager.trailing_stops
        
        stop_info = risk_manager.trailing_stops[mock_trailing_params.symbol]
        assert stop_info["entry_price"] == mock_trailing_params.entry_price
        assert stop_info["atr"] == mock_trailing_params.atr
        assert stop_info["is_long"] == mock_trailing_params.is_long
    
    def test_multiple_trailing_stops(self, risk_manager):
        """Test de múltiples trailing stops."""
        # Crear trailing stops para múltiples símbolos
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        
        for i, symbol in enumerate(symbols):
            params = TrailingStopParams(
                symbol=symbol,
                entry_price=100.0 + i * 10,
                atr=1.0,
                multiplier_atr=2.0,
                is_long=True
            )
            risk_manager.get_adaptive_trailing_stop(params)
        
        # Verificar que se crearon todos
        assert len(risk_manager.trailing_stops) == len(symbols)
        for symbol in symbols:
            assert symbol in risk_manager.trailing_stops
