"""Unit tests for trading mode clarity (P0 slice S1)."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.core.trading_mode import compute_effective_mode, get_trading_mode_snapshot


# El `gate` es explícito en cada caso: estos casos testean el álgebra de flags,
# no la política del live gate (ADR-007). Con gate firmado, un flag apagado o
# EMERGENCY_STOP siguen bloqueando; sin gate firmado nada arma (ver
# test_default_gate_is_fail_closed).
@pytest.mark.parametrize(
    "paper,force,enabled,emergency,gate,expected",
    [
        (True, False, True, False, False, "paper"),
        (True, True, True, False, True, "real_armed"),  # force overrides paper intent
        (False, False, True, False, True, "real_blocked"),
        (False, True, False, False, True, "real_blocked"),
        (False, True, True, True, True, "real_blocked"),
        (False, True, True, False, True, "real_armed"),
    ],
)
def test_compute_effective_mode(paper, force, enabled, emergency, gate, expected):
    assert (
        compute_effective_mode(
            paper_trading=paper,
            force_real_mode=force,
            trading_enabled=enabled,
            emergency_stop=emergency,
            live_gate_signed=gate,
        )
        == expected
    )


def test_default_gate_is_fail_closed():
    """Omitir live_gate_signed significa "gate no verificado": nunca real_armed.

    Protege contra el refactor que olvida propagar el parámetro el día que hay
    dinero real en la cuenta.
    """
    assert (
        compute_effective_mode(
            paper_trading=False,
            force_real_mode=True,
            trading_enabled=True,
            emergency_stop=False,
        )
        == "real_blocked"
    )


def test_snapshot_paper_from_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    snap = get_trading_mode_snapshot()
    assert snap["paper_trading"] is True
    assert snap["effective_mode"] == "paper"
    assert "api_key" not in snap
    assert "secret" not in snap


def test_snapshot_real_blocked_without_force(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    snap = get_trading_mode_snapshot()
    assert snap["effective_mode"] == "real_blocked"
