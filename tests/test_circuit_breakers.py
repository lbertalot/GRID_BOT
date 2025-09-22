#!/usr/bin/env python3
"""
Test para validar que los circuit breakers funcionan correctamente
"""

import pytest
import asyncio
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.circuit_breakers import CircuitBreakers


class TestCircuitBreakers:
    """Test para validar funcionamiento de circuit breakers"""
    
    def test_circuit_breakers_initialization(self):
        """Test que los circuit breakers se inicializan correctamente"""
        cb = CircuitBreakers()
        
        # Verificar que todos los breakers están inactivos inicialmente
        assert not cb.is_critical_mode_active()
        assert not cb.is_breaker_active('balance_discrepancy')
        assert not cb.is_breaker_active('operation_failure_rate')
        assert not cb.is_breaker_active('system_integrity')
    
    @pytest.mark.asyncio
    async def test_activate_breaker(self):
        """Test que se puede activar un circuit breaker"""
        cb = CircuitBreakers()
        
        # Activar un breaker
        result = await cb.activate_breaker('system_integrity', 'Test activation')
        
        assert result is True
        assert cb.is_breaker_active('system_integrity')
        
        # Verificar que el estado se actualiza correctamente
        status = cb.get_breaker_status('system_integrity')
        assert status['active'] is True
        assert status['reason'] == 'Test activation'
        assert status['activated_at'] is not None
    
    @pytest.mark.asyncio
    async def test_deactivate_breaker(self):
        """Test que se puede desactivar un circuit breaker"""
        cb = CircuitBreakers()
        
        # Activar y luego desactivar
        await cb.activate_breaker('system_integrity', 'Test activation')
        assert cb.is_breaker_active('system_integrity')
        
        result = await cb.deactivate_breaker('system_integrity')
        assert result is True
        assert not cb.is_breaker_active('system_integrity')
    
    @pytest.mark.asyncio
    async def test_critical_mode(self):
        """Test que el modo crítico activa todos los breakers"""
        cb = CircuitBreakers()
        
        # Activar modo crítico
        result = await cb.activate_critical_mode()
        assert result is True
        assert cb.is_critical_mode_active()
        
        # Verificar que todos los breakers están activos
        for breaker_type in cb.breakers:
            assert cb.is_breaker_active(breaker_type)
    
    def test_get_all_breakers_status(self):
        """Test que get_all_breakers_status funciona correctamente"""
        cb = CircuitBreakers()
        
        status = cb.get_all_breakers_status()
        
        # Verificar estructura del status
        assert 'critical_mode' in status
        assert 'active_breakers' in status
        assert 'total_active' in status
        assert 'breakers' in status
        
        # En estado inicial, no debería haber breakers activos
        assert status['critical_mode'] is False
        assert len(status['active_breakers']) == 0
        assert status['total_active'] == 0
    
    @pytest.mark.asyncio
    async def test_breaker_activation_with_loss_simulation(self):
        """Test que simula pérdidas y activa circuit breakers"""
        cb = CircuitBreakers()
        
        # Simular pérdida crítica que debería activar breakers
        await cb.activate_breaker('balance_discrepancy', 'Pérdida crítica detectada: -331% ROI')
        
        # Verificar que el breaker se activó
        assert cb.is_breaker_active('balance_discrepancy')
        
        # Verificar que get_all_breakers_status refleja el estado
        status = cb.get_all_breakers_status()
        assert 'balance_discrepancy' in status['active_breakers']
        assert status['total_active'] == 1
    
    def test_breaker_summary_generation(self):
        """Test que se puede generar un resumen de breakers"""
        cb = CircuitBreakers()
        
        summary = cb.get_breaker_summary()
        
        # Verificar que el resumen contiene información básica
        assert "CIRCUIT BREAKERS" in summary
        assert "balance_discrepancy" in summary
        assert "system_integrity" in summary
        assert "operation_failure_rate" in summary
        assert "critical_mode" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
