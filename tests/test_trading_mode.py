"""Unit tests for trading mode clarity (P0 slice S1)."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.core.trading_mode import compute_effective_mode, get_trading_mode_snapshot


@pytest.mark.parametrize(
    "paper,force,enabled,emergency,expected",
    [
        (True, False, True, False, "paper"),
        (True, True, True, False, "real_armed"),  # force overrides paper intent
        (False, False, True, False, "real_blocked"),
        (False, True, False, False, "real_blocked"),
        (False, True, True, True, "real_blocked"),
        (False, True, True, False, "real_armed"),
    ],
)
def test_compute_effective_mode(paper, force, enabled, emergency, expected):
    assert (
        compute_effective_mode(
            paper_trading=paper,
            force_real_mode=force,
            trading_enabled=enabled,
            emergency_stop=emergency,
        )
        == expected
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
