"""
S-BREAKERS B1 + B4 — estado compartido y contrato de cooldown.

B1: AutoCircuitBreaker / API / worker deben ver la misma instancia
    (`get_shared_breakers()`), no `CircuitBreakers()` frescos.

B4: El cooldown 300s es anti-flap del *mismo evento* (misma razón),
    no un silenciador de trips de pérdida reales distintos.
"""

from __future__ import annotations

import pytest

from app.core.auto_circuit_breaker import AutoCircuitBreaker
from app.core.breaker_visibility import get_breaker_visibility_snapshot
from app.core.circuit_breakers import (
    CircuitBreakers,
    get_shared_breakers,
    reset_shared_breakers,
)


@pytest.fixture(autouse=True)
def _isolate_shared_breakers():
    """Cada test parte de un singleton limpio."""
    reset_shared_breakers()
    yield
    reset_shared_breakers()


def test_get_shared_breakers_es_singleton():
    a = get_shared_breakers()
    b = get_shared_breakers()
    assert a is b


def test_auto_circuit_breaker_usa_shared_breakers():
    """B1: AutoCircuitBreaker no debe crear un CircuitBreakers privado."""
    shared = get_shared_breakers()
    auto = AutoCircuitBreaker()
    assert auto.breakers is shared


@pytest.mark.asyncio
async def test_activacion_via_auto_visible_en_snapshot_api():
    """B1: lo que activa AutoCircuitBreaker debe verse en el snapshot API."""
    auto = AutoCircuitBreaker()
    ok = await auto.breakers.activate_breaker(
        "balance_discrepancy", "pérdida diaria paper-test"
    )
    assert ok is True

    snapshot = get_breaker_visibility_snapshot(get_shared_breakers())
    assert snapshot["any_open"] is True
    open_names = {
        b["name"] for b in snapshot["breakers"] if b.get("state") == "open"
    }
    assert "balance_discrepancy" in open_names


@pytest.mark.asyncio
async def test_circuit_breakers_fresco_no_es_fuente_de_verdad():
    """Documenta el anti-patrón: CircuitBreakers() nuevo no ve trips reales."""
    shared = get_shared_breakers()
    await shared.activate_breaker("system_integrity", "trip real worker")
    fresco = CircuitBreakers()
    assert fresco.is_breaker_active("system_integrity") is False
    assert shared.is_breaker_active("system_integrity") is True
    assert get_shared_breakers().is_breaker_active("system_integrity") is True


@pytest.fixture
def cb_cooldown() -> CircuitBreakers:
    """Instancia aislada con cooldown alto (no el singleton)."""
    cb = CircuitBreakers()
    cb._cooldown_seconds = 300
    return cb


@pytest.mark.asyncio
async def test_cooldown_bloquea_mismo_evento_anti_flap(cb_cooldown):
    """Contrato B4: misma razón dentro de la ventana → omitir (anti-flap)."""
    cb = cb_cooldown
    reason = "pérdida diaria excedida: 6.00% > 5.00%"

    assert await cb.activate_breaker("balance_discrepancy", reason) is True
    await cb.deactivate_breaker("balance_discrepancy")

    ok = await cb.activate_breaker("balance_discrepancy", reason)
    assert ok is False
    assert cb.is_breaker_active("balance_discrepancy") is False


@pytest.mark.asyncio
async def test_cooldown_permite_trip_de_perdida_distinto(cb_cooldown):
    """Contrato B4: razón distinta = evento real distinto → debe abrir."""
    cb = cb_cooldown

    assert (
        await cb.activate_breaker(
            "balance_discrepancy", "pérdida diaria excedida: 6.00% > 5.00%"
        )
        is True
    )
    await cb.deactivate_breaker("balance_discrepancy")
    assert cb.is_breaker_active("balance_discrepancy") is False

    ok = await cb.activate_breaker(
        "balance_discrepancy",
        "pérdida total excedida: 12.00% > 10.00%",
    )
    assert ok is True, (
        "Cooldown no debe tragar trips de pérdida real con razón distinta"
    )
    assert cb.is_breaker_active("balance_discrepancy") is True
    status = cb.get_breaker_status("balance_discrepancy")
    assert "pérdida total" in (status.get("reason") or "")


@pytest.mark.asyncio
async def test_critical_mode_ignora_cooldown(cb_cooldown):
    """Modo crítico es emergencia: bypass del cooldown anti-flap."""
    cb = cb_cooldown
    await cb.activate_breaker("system_integrity", "primer evento")
    await cb.deactivate_breaker("system_integrity")

    ok = await cb.activate_critical_mode()
    assert ok is True
    assert cb.is_critical_mode_active() is True
    assert cb.is_trading_halted() is True


def test_activate_breaker_docstring_documenta_contrato_cooldown():
    """El contrato B4 debe vivir en el docstring de activate_breaker."""
    doc = CircuitBreakers.activate_breaker.__doc__ or ""
    lowered = doc.lower()
    assert "anti-flap" in lowered or "mismo" in lowered
    assert "cooldown" in lowered
