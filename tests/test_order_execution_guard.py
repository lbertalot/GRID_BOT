"""S-GATE: órdenes reales solo con effective_mode=real_armed (B15/B26)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.order_execution_guard import RealOrderBlocked, assert_real_order_allowed


def test_paper_mode_blocks_real_order(paper_env, monkeypatch):
    # Override kill-switch off so the PAPER branch (not EMERGENCY) is asserted.
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.delenv("LIVE_GATE_PATH", raising=False)
    monkeypatch.delenv("LIVE_GATE_DIR", raising=False)
    with pytest.raises(RealOrderBlocked) as exc:
        assert_real_order_allowed(context="test")
    assert "PAPER_TRADING" in exc.value.reason or "paper" in exc.value.reason.lower()
    assert exc.value.snapshot.get("effective_mode") == "paper"


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


def test_force_real_mode_missing_reason(monkeypatch, tmp_path):
    """Non-paper + trading on without FORCE_REAL_MODE → dedicated reason."""
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    monkeypatch.setenv("LIVE_GATE_DIR", str(tmp_path / "empty_gates"))
    (tmp_path / "empty_gates").mkdir()
    with pytest.raises(RealOrderBlocked) as exc:
        assert_real_order_allowed(context="no-force")
    assert exc.value.reason == "FORCE_REAL_MODE not set"


def test_inconsistent_snapshot_falls_back_to_mode_reason(monkeypatch):
    """Defensive else: flags look armed but effective_mode is not real_armed."""
    import app.core.order_execution_guard as guard

    def _weird_snap():
        return {
            "effective_mode": "real_blocked",
            "emergency_stop": False,
            "trading_enabled": True,
            "paper_trading": False,
            "force_real_mode": True,
            "live_gate_signed": True,
        }

    monkeypatch.setattr(
        "app.core.trading_mode.get_trading_mode_snapshot", _weird_snap
    )
    with pytest.raises(RealOrderBlocked) as exc:
        guard.assert_real_order_allowed(context="inconsistent")
    assert exc.value.reason == "effective_mode=real_blocked"


def test_paper_env_blocks_without_context_label(paper_env):
    with pytest.raises(RealOrderBlocked) as exc:
        assert_real_order_allowed()
    assert "real_order_blocked" in str(exc.value)
