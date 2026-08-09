"""Unit tests for trading mode clarity (P0 slice S1 + S-COV-85 COV-1.1)."""

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
        (True, False, False, True, False, "paper"),
        (True, True, True, False, True, "real_armed"),  # force overrides paper intent
        (True, True, True, False, False, "real_blocked"),
        (False, False, True, False, True, "real_blocked"),
        (False, True, False, False, True, "real_blocked"),
        (False, True, True, True, True, "real_blocked"),
        (False, True, True, False, False, "real_blocked"),
        (False, True, True, False, True, "real_armed"),
        (False, False, False, False, False, "real_blocked"),
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


def test_paper_env_fixture_keeps_snapshot_paper(paper_env):
    """COV-0.3 / COV-1.1: fixture pack never arms real mode."""
    snap = get_trading_mode_snapshot()
    assert snap["paper_trading"] is True
    assert snap["force_real_mode"] is False
    assert snap["trading_enabled"] is False
    assert snap["emergency_stop"] is True
    assert snap["effective_mode"] == "paper"
    assert snap["live_gate_signed"] is False


@pytest.mark.parametrize(
    "flag,value",
    [
        ("PAPER_TRADING", "1"),
        ("PAPER_TRADING", "YES"),
        ("PAPER_TRADING", "on"),
    ],
)
def test_env_bool_truthy_aliases(monkeypatch, flag, value):
    monkeypatch.setenv(flag, value)
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("EMERGENCY_STOP", "true")
    assert get_trading_mode_snapshot()["paper_trading"] is True


def test_snapshot_includes_binance_testnet_flag(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("BINANCE_TESTNET", "true")
    snap = get_trading_mode_snapshot()
    assert snap["binance_testnet"] is True
    assert snap["effective_mode"] == "paper"
