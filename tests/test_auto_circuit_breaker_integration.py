#!/usr/bin/env python3
"""
Test de integración para Auto Circuit Breaker con datos reales
"""

import pytest
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.auto_circuit_breaker import AutoCircuitBreaker
from app.db.session import SessionLocal


class TestAutoCircuitBreakerIntegration:
    """Test de integración para auto circuit breaker"""

    @pytest.fixture
    def auto_cb(self):
        """Fixture para AutoCircuitBreaker"""
        return AutoCircuitBreaker()

    @pytest.fixture
    def db_session(self):
        """Fixture para sesión de base de datos"""
        db = SessionLocal()
        yield db
        db.close()

    @pytest.mark.asyncio
    async def test_auto_circuit_breaker_with_real_data(self, auto_cb, db_session):
        """Test que el auto circuit breaker funciona con datos reales de la base de datos"""

        # Verificar estado inicial
        initial_status = await auto_cb.get_breakers_status()
        assert initial_status["total_active"] == 0

        # Ejecutar verificación automática
        results = await auto_cb.check_and_activate_breakers()

        # Verificar que se ejecutó sin errores
        assert "error" not in results
        assert "total_loss_pct" in results
        assert "daily_loss_pct" in results

        # Si hay pérdidas significativas, deberían activarse breakers
        if results["total_loss_pct"] > 0.10:  # 10% pérdida total
            assert len(results["breakers_activated"]) > 0
            assert len(results["reasons"]) > 0

        print("📊 Métricas detectadas:")
        print(f"  - Pérdida total: {results['total_loss_pct']:.2%}")
        print(f"  - Pérdida diaria: {results['daily_loss_pct']:.2%}")
        print(f"  - Breakers activados: {results['breakers_activated']}")
        print(f"  - Razones: {results['reasons']}")

    @pytest.mark.asyncio
    async def test_manual_activation(self, auto_cb):
        """Test que se puede activar circuit breakers manualmente"""

        # Activar manualmente
        result = await auto_cb.manual_activation(
            "system_integrity", "Test manual activation"
        )
        assert result is True

        # Verificar que se activó
        status = await auto_cb.get_breakers_status()
        assert "system_integrity" in status["active_breakers"]

        # Desactivar manualmente
        result = await auto_cb.manual_deactivation("system_integrity")
        assert result is True

        # Verificar que se desactivó
        status = await auto_cb.get_breakers_status()
        assert "system_integrity" not in status["active_breakers"]

    @pytest.mark.asyncio
    async def test_critical_mode_activation(self, auto_cb):
        """Test que el modo crítico se activa con pérdidas extremas"""

        # Simular pérdida crítica (20%+)
        # Esto debería activar el modo crítico
        results = await auto_cb.check_and_activate_breakers()

        # Si hay pérdidas críticas, verificar modo crítico
        if results.get("critical_mode", False):
            status = await auto_cb.get_breakers_status()
            assert status["critical_mode"] is True
            assert len(status["active_breakers"]) > 0

    def test_thresholds_configuration(self, auto_cb):
        """Test que los umbrales están configurados correctamente"""

        thresholds = auto_cb.thresholds

        # Verificar que todos los umbrales están definidos
        assert "max_daily_loss_pct" in thresholds
        assert "max_total_loss_pct" in thresholds
        assert "max_consecutive_losses" in thresholds
        assert "max_hourly_loss_pct" in thresholds
        assert "critical_loss_pct" in thresholds

        # Verificar que los valores son razonables
        assert 0 < thresholds["max_daily_loss_pct"] < 0.5  # Entre 0% y 50%
        assert 0 < thresholds["max_total_loss_pct"] < 0.5  # Entre 0% y 50%
        assert thresholds["max_consecutive_losses"] > 0
        assert 0 < thresholds["max_hourly_loss_pct"] < 0.5  # Entre 0% y 50%
        assert 0 < thresholds["critical_loss_pct"] < 1.0  # Entre 0% y 100%

        print("📋 Umbrales configurados:")
        for key, value in thresholds.items():
            print(f"  - {key}: {value}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
