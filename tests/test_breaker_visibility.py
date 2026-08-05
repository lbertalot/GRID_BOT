"""Tests de visibilidad de circuit breakers (P0 slice S7).

Objetivo: un operador debe poder ver de un vistazo si hay breakers abiertos,
por qué y desde cuándo. Este slice SOLO agrega visibilidad: ningún test aquí
debe habilitar live ni relajar un umbral.

Política: 100% offline (TESTING_RULES §1). Sin red, sin exchange real.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.core.breaker_visibility import (
    BREAKER_STATE_CLOSED,
    BREAKER_STATE_HALF_OPEN,
    BREAKER_STATE_OPEN,
    get_breaker_visibility_snapshot,
)
from app.core.circuit_breakers import CircuitBreakers

REQUIRED_BREAKER_KEYS = {
    "name",
    "state",
    "reason",
    "opened_at",
    "cooldown_remaining_s",
    "failure_count",
    "threshold",
}

SENSITIVE_MARKERS = ("api_key", "apikey", "secret", "password", "token", "passphrase")


@pytest.fixture
def cb_no_cooldown(monkeypatch) -> CircuitBreakers:
    """Breakers con cooldown=0 para transiciones deterministas."""
    monkeypatch.setenv("CB_COOLDOWN_SECONDS", "0")
    return CircuitBreakers()


@pytest.fixture
def cb_long_cooldown(monkeypatch) -> CircuitBreakers:
    """Breakers con cooldown alto para observar la ventana half-open."""
    monkeypatch.setenv("CB_COOLDOWN_SECONDS", "3600")
    return CircuitBreakers()


@pytest.fixture(autouse=True)
def _paper_env(monkeypatch):
    """Entorno paper-first explícito: ningún test arma modo real."""
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("EMERGENCY_STOP", "false")


def _by_name(snapshot: dict, name: str) -> dict:
    return next(b for b in snapshot["breakers"] if b["name"] == name)


# ─────────────────────────────────────────────────────────────────
# Estado cerrado
# ─────────────────────────────────────────────────────────────────


def test_snapshot_todos_cerrados_por_defecto(cb_no_cooldown):
    snapshot = get_breaker_visibility_snapshot(cb_no_cooldown)

    assert snapshot["any_open"] is False
    assert snapshot["emergency_stop"] is False
    assert snapshot["open_count"] == 0
    assert len(snapshot["breakers"]) == len(cb_no_cooldown.breakers)
    for breaker in snapshot["breakers"]:
        assert breaker["state"] == BREAKER_STATE_CLOSED
        assert breaker["reason"] is None
        assert breaker["opened_at"] is None
        assert breaker["cooldown_remaining_s"] == 0.0


# ─────────────────────────────────────────────────────────────────
# Estado abierto: razón + timestamp
# ─────────────────────────────────────────────────────────────────


async def test_breaker_abierto_expone_razon_y_timestamp(cb_no_cooldown):
    await cb_no_cooldown.activate_breaker(
        "balance_discrepancy", "Discrepancia de balance 3.2% > 1.0%"
    )

    snapshot = get_breaker_visibility_snapshot(cb_no_cooldown)
    breaker = _by_name(snapshot, "balance_discrepancy")

    assert snapshot["any_open"] is True
    assert snapshot["open_count"] == 1
    assert breaker["state"] == BREAKER_STATE_OPEN
    assert breaker["reason"] == "Discrepancia de balance 3.2% > 1.0%"
    # opened_at debe ser un ISO-8601 parseable para el dashboard
    assert isinstance(datetime.fromisoformat(breaker["opened_at"]), datetime)


async def test_failure_count_cuenta_aperturas(cb_no_cooldown):
    await cb_no_cooldown.activate_breaker("system_integrity", "primera")
    await cb_no_cooldown.deactivate_breaker("system_integrity")
    await cb_no_cooldown.activate_breaker("system_integrity", "segunda")

    breaker = _by_name(
        get_breaker_visibility_snapshot(cb_no_cooldown), "system_integrity"
    )
    assert breaker["failure_count"] == 2


def test_cada_breaker_expone_su_umbral(cb_no_cooldown):
    snapshot = get_breaker_visibility_snapshot(cb_no_cooldown)
    for breaker in snapshot["breakers"]:
        assert breaker["threshold"] is not None
        assert isinstance(breaker["threshold"], (int, float))


# ─────────────────────────────────────────────────────────────────
# Half-open: ventana de cooldown tras el reset
# ─────────────────────────────────────────────────────────────────


async def test_half_open_reporta_cooldown_restante(cb_long_cooldown):
    """Tras cerrar un breaker sigue habiendo cooldown que impide re-abrirlo:
    para el operador eso es half-open, no closed."""
    await cb_long_cooldown.activate_breaker("operation_failure_rate", "fallos API")
    await cb_long_cooldown.deactivate_breaker("operation_failure_rate")

    breaker = _by_name(
        get_breaker_visibility_snapshot(cb_long_cooldown), "operation_failure_rate"
    )

    assert breaker["state"] == BREAKER_STATE_HALF_OPEN
    assert 0 < breaker["cooldown_remaining_s"] <= 3600
    # half-open no cuenta como abierto para el agregado
    assert get_breaker_visibility_snapshot(cb_long_cooldown)["any_open"] is False


async def test_cooldown_agotado_vuelve_a_closed(cb_no_cooldown):
    await cb_no_cooldown.activate_breaker("operation_failure_rate", "fallos API")
    await cb_no_cooldown.deactivate_breaker("operation_failure_rate")

    breaker = _by_name(
        get_breaker_visibility_snapshot(cb_no_cooldown), "operation_failure_rate"
    )
    assert breaker["state"] == BREAKER_STATE_CLOSED
    assert breaker["cooldown_remaining_s"] == 0.0


# ─────────────────────────────────────────────────────────────────
# Agregados: any_open / emergency_stop
# ─────────────────────────────────────────────────────────────────


async def test_multiples_breakers_abiertos_marcan_any_open(cb_no_cooldown):
    await cb_no_cooldown.activate_breaker("balance_discrepancy", "a")
    await cb_no_cooldown.activate_breaker("system_integrity", "b")

    snapshot = get_breaker_visibility_snapshot(cb_no_cooldown)

    assert snapshot["any_open"] is True
    assert snapshot["open_count"] == 2
    abiertos = {
        b["name"] for b in snapshot["breakers"] if b["state"] == BREAKER_STATE_OPEN
    }
    assert abiertos == {"balance_discrepancy", "system_integrity"}


def test_emergency_stop_refleja_env(cb_no_cooldown, monkeypatch):
    monkeypatch.setenv("EMERGENCY_STOP", "true")
    snapshot = get_breaker_visibility_snapshot(cb_no_cooldown)
    assert snapshot["emergency_stop"] is True


async def test_emergency_stop_refleja_modo_critico(cb_no_cooldown):
    await cb_no_cooldown.activate_critical_mode()
    snapshot = get_breaker_visibility_snapshot(cb_no_cooldown)
    assert snapshot["emergency_stop"] is True
    assert snapshot["any_open"] is True


# ─────────────────────────────────────────────────────────────────
# Seguridad del payload
# ─────────────────────────────────────────────────────────────────


async def test_payload_no_expone_claves_sensibles(cb_no_cooldown, monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "no-debe-aparecer")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "tampoco-debe-aparecer")
    await cb_no_cooldown.activate_breaker("balance_discrepancy", "x")

    raw = json.dumps(get_breaker_visibility_snapshot(cb_no_cooldown)).lower()

    for marker in SENSITIVE_MARKERS:
        assert marker not in raw
    assert "no-debe-aparecer" not in raw
    assert "tampoco-debe-aparecer" not in raw


# ─────────────────────────────────────────────────────────────────
# Contrato HTTP (consumido por el dashboard CEO — Track C)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/breakers/status", "/api/breakers/status"])
def test_endpoint_status_contrato_de_keys(client, path):
    response = client.get(path)

    assert response.status_code == 200
    payload = response.json()
    assert {"generated_at", "any_open", "emergency_stop", "open_count", "breakers"} <= (
        set(payload.keys())
    )
    assert isinstance(payload["breakers"], list)
    assert payload["breakers"], "el status debe listar todos los breakers conocidos"
    for breaker in payload["breakers"]:
        assert REQUIRED_BREAKER_KEYS <= set(breaker.keys())
        assert breaker["state"] in {
            BREAKER_STATE_CLOSED,
            BREAKER_STATE_OPEN,
            BREAKER_STATE_HALF_OPEN,
        }


def test_endpoint_status_no_filtra_secretos(client):
    raw = client.get("/api/breakers/status").text.lower()
    for marker in SENSITIVE_MARKERS:
        assert marker not in raw


def test_summary_legacy_mantiene_contrato(client):
    """El contrato existente de /breakers/summary no debe romperse."""
    payload = client.get("/breakers/summary").json()
    assert {"critical_mode", "active_breakers", "total_active", "breakers"} <= set(
        payload.keys()
    )


# ─────────────────────────────────────────────────────────────────
# Métricas Prometheus
# ─────────────────────────────────────────────────────────────────


async def test_snapshot_publica_metricas_prometheus(cb_no_cooldown):
    from app.core.metrics import (
        breaker_any_open,
        breaker_opens_total,
        breaker_state,
        emergency_stop_active,
    )

    antes = breaker_opens_total.labels(type="balance_discrepancy")._value.get()
    await cb_no_cooldown.activate_breaker("balance_discrepancy", "x")
    get_breaker_visibility_snapshot(cb_no_cooldown)

    assert breaker_opens_total.labels(type="balance_discrepancy")._value.get() == (
        antes + 1
    )
    assert breaker_state.labels(type="balance_discrepancy")._value.get() == 1
    assert breaker_any_open._value.get() == 1
    assert emergency_stop_active._value.get() == 0


def test_metricas_de_breakers_expuestas_en_prometheus(client, cb_no_cooldown):
    get_breaker_visibility_snapshot(cb_no_cooldown)
    body = client.get("/metrics").text

    assert "breaker_state" in body
    assert "breaker_opens_total" in body
    assert "breaker_any_open" in body
    assert "emergency_stop_active" in body
