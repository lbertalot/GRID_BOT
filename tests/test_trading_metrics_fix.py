#!/usr/bin/env python3
"""
Test unitario para validar la corrección del sistema de métricas TradingMetrics
"""

import pytest
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.metrics import TradingMetrics, trades_executed_total, trades_success_rate


class TestTradingMetricsFix:
    """Test para validar que TradingMetrics tiene todos los atributos necesarios"""
    
    def test_trading_metrics_has_required_attributes(self):
        """Test que TradingMetrics tiene todos los atributos necesarios"""
        metrics = TradingMetrics()
        
        # Verificar que los atributos existen
        assert hasattr(metrics, 'trades_executed_total'), "trades_executed_total debe existir"
        assert hasattr(metrics, 'trades_success_rate'), "trades_success_rate debe existir"
        
        # Verificar que son las métricas correctas
        assert metrics.trades_executed_total == trades_executed_total
        assert metrics.trades_success_rate == trades_success_rate
    
    def test_trades_executed_total_metric_exists(self):
        """Test que la métrica trades_executed_total está definida globalmente"""
        assert trades_executed_total is not None
        assert trades_executed_total._name == 'trades_executed'
        assert trades_executed_total._type == 'counter'
    
    def test_trades_success_rate_metric_exists(self):
        """Test que la métrica trades_success_rate está definida globalmente"""
        assert trades_success_rate is not None
        assert trades_success_rate._name == 'trades_success_rate'
        assert trades_success_rate._type == 'gauge'
    
    def test_trading_metrics_can_increment_trades(self):
        """Test que se puede incrementar trades_executed_total sin errores"""
        metrics = TradingMetrics()
        
        # Esto no debería lanzar AttributeError
        try:
            metrics.trades_executed_total.labels(side="BUY", asset="BTCUSDT", strategy="grid").inc(1)
            metrics.trades_executed_total.labels(side="SELL", asset="BTCUSDT", strategy="grid").inc(1)
            success = True
        except AttributeError as e:
            success = False
            print(f"Error: {e}")
        
        assert success, "No se debe lanzar AttributeError al incrementar trades_executed_total"
    
    def test_trading_metrics_can_set_success_rate(self):
        """Test que se puede establecer trades_success_rate sin errores"""
        metrics = TradingMetrics()
        
        # Esto no debería lanzar AttributeError
        try:
            metrics.trades_success_rate.labels(strategy="grid").set(0.75)
            success = True
        except AttributeError as e:
            success = False
            print(f"Error: {e}")
        
        assert success, "No se debe lanzar AttributeError al establecer trades_success_rate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
