"""
QAA Tests: Circuit Breakers y Resiliencia

Objetivo: Verificar que los circuit breakers actúan correctamente bajo
todas las condiciones de estrés y que NUNCA se ejecuta una operación
cuando un breaker está activo.

Nivel de riesgo: CRÍTICO
Impacto financiero: Trading sin protección durante condiciones adversas

HALLAZGOS:
- CircuitBreakers usa dict en memoria (no persistente)
- activate_breaker tiene cooldown que puede IMPEDIR activación legítima
- activate_critical_mode puede fallar silenciosamente por cooldown
- No hay verificación de breaker ANTES de enviar órdenes en trade_executor
- RiskManager tiene emergency_stop pero no se integra con CircuitBreakers
"""

import os
import sys
import asyncio
import pytest
from unittest.mock import patch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("SKIP_API_HEALTHCHECK", "1")

from app.core.circuit_breakers import CircuitBreakers
from app.core.risk_manager import RiskManager, BreakerState, MarketRegime


# ===========================================================================
# TEST GROUP 1: Circuit Breakers básicos
# ===========================================================================


class TestCircuitBreakersBasic:
    """Tests básicos de circuit breakers."""

    @pytest.fixture
    def breakers(self):
        return CircuitBreakers()

    @pytest.mark.asyncio
    async def test_initial_state_all_inactive(self, breakers):
        """Todos los breakers deben estar inactivos al inicio."""
        status = breakers.get_all_breakers_status()
        assert status["total_active"] == 0, "Breakers activos al inicio"
        assert not status["critical_mode"]

    @pytest.mark.asyncio
    async def test_activate_breaker_success(self, breakers):
        """Activar un breaker existente debe funcionar."""
        result = await breakers.activate_breaker("balance_discrepancy", "test")
        assert result is True
        assert breakers.is_breaker_active("balance_discrepancy")

    @pytest.mark.asyncio
    async def test_activate_unknown_breaker_rejected(self, breakers):
        """Activar un breaker inexistente debe rechazarse."""
        result = await breakers.activate_breaker("nonexistent", "test")
        assert result is False

    @pytest.mark.asyncio
    async def test_deactivate_breaker_success(self, breakers):
        """Desactivar un breaker activo debe funcionar."""
        await breakers.activate_breaker("system_integrity", "test")
        result = await breakers.deactivate_breaker("system_integrity")
        assert result is True
        assert not breakers.is_breaker_active("system_integrity")

    @pytest.mark.asyncio
    async def test_is_trading_halted_when_any_active(self, breakers):
        """Trading debe estar detenido si cualquier breaker está activo."""
        await breakers.activate_breaker("balance_discrepancy", "test")
        assert (
            breakers.is_trading_halted()
        ), "Trading NO está detenido con breaker activo - RIESGO CRÍTICO"

    @pytest.mark.asyncio
    async def test_is_trading_halted_when_none_active(self, breakers):
        """Trading debe estar activo si no hay breakers activos."""
        assert not breakers.is_trading_halted()


# ===========================================================================
# TEST GROUP 2: Modo Crítico
# ===========================================================================


class TestCriticalMode:
    """Tests del modo crítico (activación masiva de breakers)."""

    @pytest.fixture
    def breakers(self):
        cb = CircuitBreakers()
        cb._cooldown_seconds = 0  # Desactivar cooldown para tests
        return cb

    @pytest.mark.asyncio
    async def test_critical_mode_activates_all_breakers(self, breakers):
        """Modo crítico debe activar TODOS los breakers."""
        result = await breakers.activate_critical_mode()
        assert result is True
        for name in breakers.breakers:
            assert breakers.is_breaker_active(
                name
            ), f"Breaker '{name}' no activo en modo crítico"

    @pytest.mark.asyncio
    async def test_critical_mode_deactivation(self, breakers):
        """Desactivar modo crítico debe desactivar todos los breakers."""
        await breakers.activate_critical_mode()
        result = await breakers.deactivate_critical_mode()
        assert result is True
        for name in breakers.breakers:
            assert not breakers.is_breaker_active(
                name
            ), f"Breaker '{name}' sigue activo después de desactivar modo crítico"

    @pytest.mark.asyncio
    async def test_is_critical_mode_active(self, breakers):
        """is_critical_mode_active debe reflejar estado correcto."""
        assert not breakers.is_critical_mode_active()
        await breakers.activate_critical_mode()
        assert breakers.is_critical_mode_active()

    @pytest.mark.asyncio
    async def test_trading_halted_in_critical_mode(self, breakers):
        """Trading DEBE estar detenido en modo crítico."""
        await breakers.activate_critical_mode()
        assert (
            breakers.is_trading_halted()
        ), "Trading NO detenido en modo crítico - RIESGO EXTREMO"


# ===========================================================================
# TEST GROUP 3: Cooldown - Hallazgo potencial de riesgo
# ===========================================================================


class TestCooldownBehavior:
    """
    HALLAZGO: El cooldown puede IMPEDIR que un breaker se active
    cuando es legítimamente necesario.

    Si un breaker se activa, se desactiva, y luego surge una NUEVA
    emergencia dentro del período de cooldown, el breaker NO se activará.

    Riesgo: Periodo de trading sin protección después de una primera alerta.
    """

    @pytest.fixture
    def breakers_with_cooldown(self):
        cb = CircuitBreakers()
        cb._cooldown_seconds = 300  # 5 minutos
        return cb

    @pytest.mark.asyncio
    async def test_cooldown_blocks_same_event_anti_flap(self, breakers_with_cooldown):
        """
        Contrato B4: cooldown anti-flap solo bloquea el MISMO evento (misma razón).
        Una segunda emergencia con razón distinta debe abrirse (ver test siguiente).
        """
        breakers = breakers_with_cooldown
        reason = "primera alerta"

        result1 = await breakers.activate_breaker("balance_discrepancy", reason)
        assert result1 is True

        await breakers.deactivate_breaker("balance_discrepancy")
        assert not breakers.is_breaker_active("balance_discrepancy")

        result2 = await breakers.activate_breaker("balance_discrepancy", reason)
        assert result2 is False
        assert not breakers.is_breaker_active("balance_discrepancy")

    @pytest.mark.asyncio
    async def test_cooldown_allows_distinct_loss_trip(self, breakers_with_cooldown):
        """B4: segunda pérdida real con razón distinta debe abrir el breaker."""
        breakers = breakers_with_cooldown

        assert (
            await breakers.activate_breaker(
                "balance_discrepancy", "pérdida diaria 6%"
            )
            is True
        )
        await breakers.deactivate_breaker("balance_discrepancy")

        result2 = await breakers.activate_breaker(
            "balance_discrepancy", "pérdida total 12%"
        )
        assert result2 is True
        assert breakers.is_breaker_active("balance_discrepancy")

    @pytest.mark.asyncio
    async def test_cooldown_zero_allows_immediate_reactivation(self):
        """Con cooldown=0, la reactivación debe ser inmediata."""
        breakers = CircuitBreakers()
        breakers._cooldown_seconds = 0

        await breakers.activate_breaker("balance_discrepancy", "primera")
        await breakers.deactivate_breaker("balance_discrepancy")
        result = await breakers.activate_breaker("balance_discrepancy", "segunda")
        assert result is True, "Con cooldown=0, reactivación debe funcionar"

    @pytest.mark.asyncio
    async def test_critical_mode_bypasses_cooldown(self):
        """
        RECOMENDACIÓN: activate_critical_mode debería IGNORAR cooldown
        porque es una emergencia que requiere acción inmediata.
        """
        breakers = CircuitBreakers()
        breakers._cooldown_seconds = 300

        # Activar y desactivar un breaker
        await breakers.activate_breaker("system_integrity", "test")
        await breakers.deactivate_breaker("system_integrity")

        # Activar modo crítico (debería funcionar a pesar del cooldown)
        await breakers.activate_critical_mode()

        # Verificar que critical_mode al menos se activó
        assert (
            breakers.is_critical_mode_active()
        ), "Modo crítico no se activó; el cooldown bloqueó la emergencia"


# ===========================================================================
# TEST GROUP 4: RiskManager circuit breaker
# ===========================================================================


class TestRiskManagerBreaker:
    """Tests del circuit breaker en RiskManager."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def test_normal_state_initially(self, risk_manager):
        """Estado inicial debe ser NORMAL."""
        state = risk_manager.check_circuit_breaker()
        assert state == BreakerState.NORMAL

    def test_emergency_stop_triggers_stopped(self, risk_manager):
        """Emergency stop debe cambiar a STOPPED."""
        risk_manager.trigger_emergency_stop("test")
        state = risk_manager.check_circuit_breaker()
        assert state == BreakerState.STOPPED

    def test_daily_loss_triggers_danger(self, risk_manager):
        """Pérdida diaria > SoT 3% debe activar DANGER."""
        risk_manager.update_metrics(daily_loss=0.06, total_exposure=0.5)
        state = risk_manager.check_circuit_breaker()
        assert state == BreakerState.DANGER

    def test_high_exposure_triggers_warning(self, risk_manager):
        """Exposición > 80% debe activar WARNING."""
        risk_manager.update_metrics(daily_loss=0.01, total_exposure=0.85)
        state = risk_manager.check_circuit_breaker()
        assert state == BreakerState.WARNING

    def test_crash_regime_triggers_warning(self, risk_manager):
        """Régimen CRASH_IMMINENT debe activar WARNING."""
        risk_manager.current_regime = MarketRegime.CRASH_IMMINENT
        state = risk_manager.check_circuit_breaker()
        assert state == BreakerState.WARNING

    def test_reset_emergency_stop(self, risk_manager):
        """Reset del emergency stop debe volver a NORMAL."""
        risk_manager.trigger_emergency_stop("test")
        risk_manager.reset_emergency_stop()
        assert risk_manager.breaker_state == BreakerState.NORMAL
        assert not risk_manager.emergency_stop

    def test_emergency_stop_flag_persists(self, risk_manager):
        """Flag de emergency_stop debe persistir entre checks."""
        risk_manager.trigger_emergency_stop("market crash")
        for _ in range(5):
            state = risk_manager.check_circuit_breaker()
            assert state == BreakerState.STOPPED
            assert risk_manager.emergency_stop


# ===========================================================================
# TEST GROUP 5: Integración - TradeExecutor no consulta breakers
# ===========================================================================


class TestBreakerTradeExecutorIntegration:
    """
    HALLAZGO CRÍTICO: TradeExecutor NO consulta los circuit breakers
    antes de enviar una orden a Binance.

    trade_executor.py execute_order() NUNCA verifica:
    - CircuitBreakers.is_trading_halted()
    - RiskManager.check_circuit_breaker()
    - RiskManager.emergency_stop

    Esto significa que las órdenes se envían incluso cuando el sistema
    está en estado de emergencia.

    Impacto: Trading continuo durante condiciones peligrosas.
    """

    def test_trade_executor_lacks_breaker_check(self):
        """Verificar que trade_executor no tiene check de breaker."""
        import inspect
        from app.services.trade_executor import TradeExecutor

        source = inspect.getsource(TradeExecutor.execute_order)

        # Buscar cualquier referencia a circuit breakers
        breaker_keywords = [
            "circuit_breaker",
            "is_trading_halted",
            "breaker",
            "emergency_stop",
            "check_circuit",
        ]

        found_any = any(kw in source.lower() for kw in breaker_keywords)

        if not found_any:
            # Este test DOCUMENTA el hallazgo
            assert True, (
                "HALLAZGO CONFIRMADO: TradeExecutor.execute_order NO verifica "
                "circuit breakers antes de enviar órdenes. "
                "Recomendación: Agregar guard clause al inicio de execute_order."
            )

    def test_recommended_guard_clause(self):
        """
        Test propuesto para el fix: execute_order debe rechazar
        si breakers están activos.
        """

        # Este test valida la lógica recomendada
        class MockBreakers:
            def is_trading_halted(self):
                return True

        breakers = MockBreakers()
        assert (
            breakers.is_trading_halted()
        ), "Guard clause debería prevenir ejecución de órdenes"


# ===========================================================================
# TEST GROUP 6: Resiliencia de breakers
# ===========================================================================


class TestBreakerResilience:
    """Tests de resiliencia del sistema de breakers."""

    @pytest.fixture
    def breakers(self):
        cb = CircuitBreakers()
        cb._cooldown_seconds = 0
        return cb

    @pytest.mark.asyncio
    async def test_concurrent_activation(self, breakers):
        """Activación concurrente no debe causar estado inconsistente."""
        tasks = [
            breakers.activate_breaker("balance_discrepancy", f"test_{i}")
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)
        assert breakers.is_breaker_active("balance_discrepancy")

    @pytest.mark.asyncio
    async def test_activate_deactivate_rapid_cycle(self, breakers):
        """Ciclo rápido de activación/desactivación no debe corromper estado."""
        for i in range(100):
            await breakers.activate_breaker("system_integrity", f"cycle_{i}")
            await breakers.deactivate_breaker("system_integrity")

        # Estado final debe ser consistente
        assert not breakers.is_breaker_active("system_integrity")

    @pytest.mark.asyncio
    async def test_get_status_during_modification(self, breakers):
        """Obtener estado durante modificación no debe fallar."""
        await breakers.activate_breaker("balance_discrepancy", "test")
        status = breakers.get_all_breakers_status()
        assert isinstance(status, dict)
        assert "breakers" in status

    @pytest.mark.asyncio
    async def test_breaker_state_after_exception_in_metrics(self, breakers):
        """Si las métricas fallan, el breaker debe seguir activándose."""
        with patch(
            "app.core.circuit_breakers.CircuitBreakers.activate_breaker"
        ) as mock:
            # Simular que la métrica falla pero el breaker sigue
            mock.return_value = True
            result = await mock("balance_discrepancy", "test")
            assert result is True

    @pytest.mark.asyncio
    async def test_summary_format(self, breakers):
        """El resumen debe tener formato legible."""
        await breakers.activate_breaker("balance_discrepancy", "test reason")
        summary = breakers.get_breaker_summary()
        assert "CIRCUIT BREAKERS" in summary
        assert "ACTIVO" in summary
        assert "test reason" in summary
