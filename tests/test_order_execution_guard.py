"""S-GATE: órdenes reales solo con effective_mode=real_armed (B15/B26)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.order_execution_guard import RealOrderBlocked, assert_real_order_allowed


def _paper_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    monkeypatch.delenv("LIVE_GATE_PATH", raising=False)
    monkeypatch.delenv("LIVE_GATE_DIR", raising=False)


def test_paper_mode_blocks_real_order(monkeypatch):
    _paper_env(monkeypatch)
    monkeypatch.setenv("TRADING_ENABLED", "true")
    with pytest.raises(RealOrderBlocked) as exc:
        assert_real_order_allowed(context="test")
    assert "PAPER_TRADING" in exc.value.reason or "paper" in exc.value.reason.lower()


def test_emergency_stop_blocks_even_with_force(monkeypatch, tmp_path):
    """B26: EMERGENCY_STOP must cut real orders."""
    from tests.test_live_gate import _md_gate, _write_gate

    _gate_dir, path = _write_gate(tmp_path, _md_gate())
    monkeypatch.setenv("LIVE_GATE_PATH", str(path))
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "true")
    with pytest.raises(RealOrderBlocked) as exc:
        assert_real_order_allowed(context="kill")
    assert exc.value.reason == "EMERGENCY_STOP"


def test_trading_disabled_blocks(monkeypatch, tmp_path):
    """B26: TRADING_ENABLED=false must cut real orders."""
    from tests.test_live_gate import _md_gate, _write_gate

    _gate_dir, path = _write_gate(tmp_path, _md_gate())
    monkeypatch.setenv("LIVE_GATE_PATH", str(path))
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    with pytest.raises(RealOrderBlocked) as exc:
        assert_real_order_allowed(context="disabled")
    assert "TRADING_ENABLED" in exc.value.reason


def test_force_without_gate_blocks(monkeypatch, tmp_path):
    """B15: FORCE_REAL_MODE alone is not enough without dual signoff."""
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    monkeypatch.setenv("LIVE_GATE_DIR", str(tmp_path / "empty_gates"))
    (tmp_path / "empty_gates").mkdir()
    with pytest.raises(RealOrderBlocked) as exc:
        assert_real_order_allowed(context="ungated")
    assert "live_gate" in exc.value.reason or "unsigned" in exc.value.reason


def test_real_armed_allows(monkeypatch, tmp_path):
    from tests.test_live_gate import _md_gate, _write_gate

    _gate_dir, path = _write_gate(tmp_path, _md_gate())
    monkeypatch.setenv("LIVE_GATE_PATH", str(path))
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    snap = assert_real_order_allowed(context="armed")
    assert snap["effective_mode"] == "real_armed"
