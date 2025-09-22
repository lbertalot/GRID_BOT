#!/usr/bin/env python3
"""
Test para validar el sistema de blacklist de estrategias
"""

import pytest
import sys
import os
from datetime import datetime

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.strategy_blacklist import StrategyBlacklist


class TestStrategyBlacklist:
    """Test para validar el sistema de blacklist"""
    
    def test_blacklist_initialization(self):
        """Test que la blacklist se inicializa correctamente"""
        blacklist = StrategyBlacklist()
        
        # Verificar que SPKUSDT está en blacklist por defecto
        assert blacklist.is_symbol_blacklisted('SPKUSDT')
        assert blacklist.is_symbol_blacklisted('BTCUSDT')
        assert blacklist.is_symbol_blacklisted('AVAXUSDT')
        assert not blacklist.is_symbol_blacklisted('ETHUSDT')  # ETHUSDT es rentable
        
        # Verificar que se puede obtener la razón
        reason = blacklist.get_blacklist_reason('SPKUSDT')
        assert 'Pérdida masiva' in reason
        assert '653.96' in reason
    
    def test_blacklist_operations(self):
        """Test operaciones básicas de blacklist"""
        blacklist = StrategyBlacklist()
        
        # Agregar símbolo manualmente
        blacklist.add_symbol_to_blacklist('TESTUSDT', 'Test symbol', -50.0)
        assert blacklist.is_symbol_blacklisted('TESTUSDT')
        
        # Remover símbolo
        result = blacklist.remove_symbol_from_blacklist('TESTUSDT')
        assert result is True
        assert not blacklist.is_symbol_blacklisted('TESTUSDT')
    
    def test_strategy_blacklist(self):
        """Test blacklist de estrategias"""
        blacklist = StrategyBlacklist()
        
        # Verificar que GridTrading está bloqueada para SPKUSDT
        assert blacklist.is_strategy_blacklisted('GridTrading', 'SPKUSDT')
        assert not blacklist.is_strategy_blacklisted('GridTrading', 'ETHUSDT')
    
    def test_should_block_trading(self):
        """Test que should_block_trading funciona correctamente"""
        blacklist = StrategyBlacklist()
        
        # SPKUSDT debería estar bloqueado
        should_block, reason = blacklist.should_block_trading('SPKUSDT', 'GridTrading')
        assert should_block is True
        assert 'SPKUSDT' in reason
        assert 'blacklist' in reason
        
        # ETHUSDT debería estar permitido
        should_block, reason = blacklist.should_block_trading('ETHUSDT', 'GridTrading')
        assert should_block is False
        assert 'permitido' in reason
    
    def test_blacklist_summary(self):
        """Test que se puede generar resumen de blacklist"""
        blacklist = StrategyBlacklist()
        
        summary = blacklist.get_blacklist_summary()
        
        # Verificar que contiene información básica
        assert 'BLACKLIST SUMMARY' in summary
        assert 'SPKUSDT' in summary
        assert 'BTCUSDT' in summary
        assert 'Pérdida' in summary
    
    def test_blacklisted_symbols_list(self):
        """Test que se puede obtener lista de símbolos bloqueados"""
        blacklist = StrategyBlacklist()
        
        symbols = blacklist.get_blacklisted_symbols()
        
        # Verificar que contiene los símbolos problemáticos
        assert 'SPKUSDT' in symbols
        assert 'BTCUSDT' in symbols
        assert 'AVAXUSDT' in symbols
        assert 'BNBUSDT' in symbols
        assert 'LINKUSDT' in symbols
        
        # ETHUSDT no debería estar en la lista (es rentable)
        assert 'ETHUSDT' not in symbols
    
    def test_thresholds_configuration(self):
        """Test que los umbrales están configurados correctamente"""
        blacklist = StrategyBlacklist()
        
        thresholds = blacklist.blacklist['auto_blacklist_thresholds']
        
        # Verificar que todos los umbrales están definidos
        assert 'max_loss_per_symbol' in thresholds
        assert 'max_loss_percentage' in thresholds
        assert 'max_consecutive_losses' in thresholds
        assert 'min_trades_for_analysis' in thresholds
        
        # Verificar que los valores son razonables
        assert thresholds['max_loss_per_symbol'] < 0  # Debe ser negativo
        assert 0 < thresholds['max_loss_percentage'] < 1  # Entre 0% y 100%
        assert thresholds['max_consecutive_losses'] > 0
        assert thresholds['min_trades_for_analysis'] > 0
        
        print(f"📋 Umbrales de auto-blacklist:")
        for key, value in thresholds.items():
            print(f"  - {key}: {value}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
