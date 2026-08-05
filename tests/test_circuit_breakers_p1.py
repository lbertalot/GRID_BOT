"""
Tests P1 (FASE 3) — app/core/circuit_breakers.py
─────────────────────────────────────────────────────────────────
Objetivo: subir cobertura de 79% → ≥90% (TESTING_RULES.md §3).

Cubre:
  - activate/deactivate breaker (path feliz + tipo desconocido).
  - Cooldown anti-flapping.
  - Edge-trigger (no relogear si ya activo).
  - Modo crítico activación/desactivación.
  - Errores en métricas Prometheus (no rompen el flujo).
  - Helpers: is_breaker_active, is_trading_halted, get_breaker_status,
    get_all_breakers_status, get_breaker_summary.
  - Excepciones internas en activate/deactivate (logger.error path).
  - Parsing de CB_COOLDOWN_SECONDS inválido → fallback 300.

Política:
  - 100% offline (TESTING_RULES §1).
  - Sin red, sin DB.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.circuit_breakers import CircuitBreakers


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────


@pytest.fixture
def cb_no_cooldown(monkeypatch) -> CircuitBreakers:
    """CB con cooldown=0 para tests deterministas."""
    monkeypatch.setenv("CB_COOLDOWN_SECONDS", "0")
    return CircuitBreakers()


@pytest.fixture
def cb_long_cooldown(monkeypatch) -> CircuitBreakers:
    """CB con cooldown alto para validar bloqueo de flapping."""
    monkeypatch.setenv("CB_COOLDOWN_SECONDS", "3600")
    return CircuitBreakers()


# ─────────────────────────────────────────────────────────────────
# Activación / desactivación: path feliz
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_breaker_ok_marca_activo(cb_no_cooldown):
    ok = await cb_no_cooldown.activate_breaker("balance_discrepancy", reason="test")
    assert ok is True
    assert cb_no_cooldown.is_breaker_active("balance_discrepancy") is True
    status = cb_no_cooldown.get_breaker_status("balance_discrepancy")
    assert status["active"] is True
    assert status["reason"] == "test"
    assert status["activated_at"] is not None


@pytest.mark.asyncio
async def test_activate_breaker_default_reason(cb_no_cooldown):
    """Sin reason explícito, debe asignar texto por defecto."""
    await cb_no_cooldown.activate_breaker("system_integrity")
    status = cb_no_cooldown.get_breaker_status("system_integrity")
    assert "automáticamente" in status["reason"]


@pytest.mark.asyncio
async def test_deactivate_breaker_ok_resetea_estado(cb_no_cooldown):
    await cb_no_cooldown.activate_breaker("system_integrity", "x")
    ok = await cb_no_cooldown.deactivate_breaker("system_integrity")
    assert ok is True
    status = cb_no_cooldown.get_breaker_status("system_integrity")
    assert status["active"] is False
    assert status["activated_at"] is None
    assert status["reason"] is None


# ─────────────────────────────────────────────────────────────────
# Tipo desconocido (líneas 36-38, 68-70, 121-122, 136-137)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_breaker_tipo_desconocido_retorna_false(cb_no_cooldown):
    ok = await cb_no_cooldown.activate_breaker("nope_no_existe", "x")
    assert ok is False


@pytest.mark.asyncio
async def test_deactivate_breaker_tipo_desconocido_retorna_false(cb_no_cooldown):
    ok = await cb_no_cooldown.deactivate_breaker("nope_no_existe")
    assert ok is False


def test_is_breaker_active_tipo_desconocido_retorna_false(cb_no_cooldown):
    assert cb_no_cooldown.is_breaker_active("nope") is False


def test_get_breaker_status_tipo_desconocido_retorna_error(cb_no_cooldown):
    result = cb_no_cooldown.get_breaker_status("nope")
    assert "error" in result


# ─────────────────────────────────────────────────────────────────
# Cooldown / edge-trigger
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_breaker_edge_trigger_no_relogea(cb_no_cooldown):
    """Si ya está activo, segunda activación retorna True pero no cambia
    activated_at."""
    await cb_no_cooldown.activate_breaker("system_integrity", "first")
    first_at = cb_no_cooldown.get_breaker_status("system_integrity")["activated_at"]
    first_reason = cb_no_cooldown.get_breaker_status("system_integrity")["reason"]

    ok = await cb_no_cooldown.activate_breaker("system_integrity", "second")
    assert ok is True
    second_at = cb_no_cooldown.get_breaker_status("system_integrity")["activated_at"]
    second_reason = cb_no_cooldown.get_breaker_status("system_integrity")["reason"]
    # Edge-trigger: si ya estaba activo, no se sobreescribe.
    assert first_at == second_at
    assert first_reason == second_reason


@pytest.mark.asyncio
async def test_activate_breaker_cooldown_bloquea_mismo_evento(cb_long_cooldown):
    """Tras desactivar, reactivar con la MISMA razón dentro del cooldown
    debe omitirse (anti-flap B4). Razón distinta sí abre — ver
    tests/test_s_breakers_b1_b4.py.
    """
    reason = "mismo evento de flapping"
    ok1 = await cb_long_cooldown.activate_breaker("system_integrity", reason)
    assert ok1 is True
    await cb_long_cooldown.deactivate_breaker("system_integrity")
    ok2 = await cb_long_cooldown.activate_breaker("system_integrity", reason)
    assert ok2 is False
    assert cb_long_cooldown.is_breaker_active("system_integrity") is False


@pytest.mark.asyncio
async def test_cooldown_default_si_env_invalido(monkeypatch):
    """CB_COOLDOWN_SECONDS no parseable → fallback 300 (líneas 30-31)."""
    monkeypatch.setenv("CB_COOLDOWN_SECONDS", "not_a_number")
    cb = CircuitBreakers()
    assert cb._cooldown_seconds == 300


# ─────────────────────────────────────────────────────────────────
# Modo crítico
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_critical_mode_activa_todos(cb_no_cooldown):
    ok = await cb_no_cooldown.activate_critical_mode()
    assert ok is True
    assert cb_no_cooldown.is_critical_mode_active() is True
    assert cb_no_cooldown.is_trading_halted() is True
    status = cb_no_cooldown.get_all_breakers_status()
    assert status["total_active"] >= 1
    assert "critical_mode" in status["active_breakers"]


@pytest.mark.asyncio
async def test_deactivate_critical_mode_desactiva_todos(cb_no_cooldown):
    await cb_no_cooldown.activate_critical_mode()
    ok = await cb_no_cooldown.deactivate_critical_mode()
    assert ok is True
    assert cb_no_cooldown.is_critical_mode_active() is False
    assert cb_no_cooldown.is_trading_halted() is False


# ─────────────────────────────────────────────────────────────────
# Helpers / status
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_trading_halted_falso_cuando_todo_inactivo(cb_no_cooldown):
    assert cb_no_cooldown.is_trading_halted() is False


@pytest.mark.asyncio
async def test_get_all_breakers_status_estructura(cb_no_cooldown):
    await cb_no_cooldown.activate_breaker("balance_discrepancy", "x")
    status = cb_no_cooldown.get_all_breakers_status()
    assert set(status.keys()) == {
        "critical_mode",
        "active_breakers",
        "total_active",
        "breakers",
    }
    assert status["total_active"] == 1
    assert "balance_discrepancy" in status["active_breakers"]


@pytest.mark.asyncio
async def test_get_breaker_summary_contiene_estado(cb_no_cooldown):
    await cb_no_cooldown.activate_breaker("system_integrity", "razón_x")
    summary = cb_no_cooldown.get_breaker_summary()
    assert "system_integrity" in summary
    assert "ACTIVO" in summary
    assert "razón_x" in summary
    assert "INACTIVO" in summary  # los otros


def test_get_breaker_summary_todo_inactivo(cb_no_cooldown):
    summary = cb_no_cooldown.get_breaker_summary()
    assert "0/4 activos" in summary
    assert "INACTIVO" in summary


# ─────────────────────────────────────────────────────────────────
# Excepciones en métricas Prometheus (líneas 57-58, 80-81)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_breaker_no_falla_si_metrica_explota(cb_no_cooldown):
    """Si breaker_state.labels(...).set() lanza, NO debe romper la activación."""
    with patch("app.core.metrics.breaker_state") as mock_metric:
        mock_metric.labels.side_effect = RuntimeError("prometheus down")
        ok = await cb_no_cooldown.activate_breaker("balance_discrepancy", "x")
    assert ok is True
    assert cb_no_cooldown.is_breaker_active("balance_discrepancy") is True


@pytest.mark.asyncio
async def test_deactivate_breaker_no_falla_si_metrica_explota(cb_no_cooldown):
    await cb_no_cooldown.activate_breaker("balance_discrepancy", "x")
    with patch("app.core.metrics.breaker_state") as mock_metric:
        mock_metric.labels.side_effect = RuntimeError("prometheus down")
        ok = await cb_no_cooldown.deactivate_breaker("balance_discrepancy")
    assert ok is True
    assert cb_no_cooldown.is_breaker_active("balance_discrepancy") is False


# ─────────────────────────────────────────────────────────────────
# Excepciones internas (líneas 61-63, 84-86, 102-104, 115-117)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_breaker_captura_excepcion_interna(cb_no_cooldown):
    """Si _last_activation_ts.get() falla, retorna False (no propaga)."""
    cb_no_cooldown._last_activation_ts = None  # type: ignore[assignment]
    ok = await cb_no_cooldown.activate_breaker("balance_discrepancy", "x")
    assert ok is False


@pytest.mark.asyncio
async def test_deactivate_breaker_captura_excepcion_interna(cb_no_cooldown):
    """Si breakers[key] no es subscriptable (tupla inmutable), captura
    TypeError y retorna False."""
    # tupla inmutable: self.breakers[key]['active'] = False lanza TypeError
    cb_no_cooldown.breakers["balance_discrepancy"] = (1, 2, 3)  # type: ignore[assignment]
    ok = await cb_no_cooldown.deactivate_breaker("balance_discrepancy")
    assert ok is False


@pytest.mark.asyncio
async def test_activate_critical_mode_captura_excepcion(cb_no_cooldown):
    """Si activate_breaker explota durante critical_mode, retorna False."""
    with patch.object(
        cb_no_cooldown, "activate_breaker", side_effect=RuntimeError("boom")
    ):
        ok = await cb_no_cooldown.activate_critical_mode()
    assert ok is False


@pytest.mark.asyncio
async def test_deactivate_critical_mode_captura_excepcion(cb_no_cooldown):
    with patch.object(
        cb_no_cooldown, "deactivate_breaker", side_effect=RuntimeError("boom")
    ):
        ok = await cb_no_cooldown.deactivate_critical_mode()
    assert ok is False
