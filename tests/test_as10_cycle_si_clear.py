"""P0-C / AS-10 — no auto-clear SI de PnL en execute_trading_cycle.

Paper-only. PROMOTE_LIVE: NO. Reusa STALE_INTEGRITY_REASONS.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.trading_tasks as tt
from app.core.desk_auto_remediation import (
    STALE_INTEGRITY_REASONS,
    is_stale_net_auth_integrity_reason,
)


def _si_status(reason: str, *, active: bool = True) -> dict:
    return {
        "critical_mode": False,
        "active_breakers": ["system_integrity"] if active else [],
        "breakers": {
            "system_integrity": {"active": active, "reason": reason},
        },
    }


def test_is_stale_net_auth_integrity_reason_allowlist():
    assert is_stale_net_auth_integrity_reason("binance_net_fail") is True
    assert is_stale_net_auth_integrity_reason("BINANCE_AUTH_FAIL") is True
    assert is_stale_net_auth_integrity_reason("binance_net") is True
    assert is_stale_net_auth_integrity_reason("binance_auth") is True
    assert STALE_INTEGRITY_REASONS >= {
        "binance_net_fail",
        "binance_auth_fail",
        "binance_net",
        "binance_auth",
    }


def test_execution_blocked_pnl_si_and_critical():
    assert tt.execution_blocked_by_breakers({}) is False
    assert tt.execution_blocked_by_breakers(_si_status("binance_net_fail")) is False
    assert tt.execution_blocked_by_breakers(_si_status("binance_auth_fail")) is False
    assert (
        tt.execution_blocked_by_breakers(
            _si_status("Demasiadas pérdidas consecutivas: 5")
        )
        is True
    )
    assert (
        tt.execution_blocked_by_breakers(_si_status("IC2_flatten_core_at_deployed_dd"))
        is True
    )
    assert tt.execution_blocked_by_breakers({"critical_mode": True}) is True
    assert (
        tt.execution_blocked_by_breakers(
            _si_status("binance_net_fail", active=False)
        )
        is False
    )


def test_is_stale_refuses_pnl_and_ic2_reasons():
    assert is_stale_net_auth_integrity_reason(
        "Demasiadas pérdidas consecutivas: 5"
    ) is False
    assert is_stale_net_auth_integrity_reason("IC2_flatten_core_at_deployed_dd") is False
    assert is_stale_net_auth_integrity_reason("") is False
    assert is_stale_net_auth_integrity_reason(None) is False


def test_helper_pnl_reason_does_not_deactivate():
    ck = MagicMock()
    ck.get_all_breakers_status.return_value = _si_status(
        "Demasiadas pérdidas consecutivas: 5"
    )
    ck.deactivate_breaker = AsyncMock()

    acted = tt.maybe_deactivate_stale_system_integrity(ck)

    assert acted is False
    ck.deactivate_breaker.assert_not_called()


def test_helper_ic2_reason_does_not_deactivate():
    ck = MagicMock()
    ck.get_all_breakers_status.return_value = _si_status(
        "IC2_flatten_core_at_deployed_dd"
    )
    ck.deactivate_breaker = AsyncMock()

    acted = tt.maybe_deactivate_stale_system_integrity(ck)

    assert acted is False
    ck.deactivate_breaker.assert_not_called()


def test_helper_stale_net_deactivates():
    ck = MagicMock()
    ck.get_all_breakers_status.return_value = _si_status("binance_net_fail")
    ck.deactivate_breaker = AsyncMock()

    acted = tt.maybe_deactivate_stale_system_integrity(ck)

    assert acted is True
    ck.deactivate_breaker.assert_called_once_with("system_integrity")


def test_helper_inactive_si_noop():
    ck = MagicMock()
    ck.get_all_breakers_status.return_value = _si_status("binance_net_fail", active=False)
    ck.deactivate_breaker = AsyncMock()

    acted = tt.maybe_deactivate_stale_system_integrity(ck)

    assert acted is False
    ck.deactivate_breaker.assert_not_called()


def _pre_cycle_breakers(reason: str):
    singleton = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": True,
        "auth_ok": True,
    }
    breakers = MagicMock()
    breakers.deactivate_breaker = AsyncMock()
    breakers.activate_breaker = AsyncMock()
    breakers.get_all_breakers_status.return_value = _si_status(reason)
    return singleton, breakers


def test_execute_trading_cycle_keeps_pnl_si_after_validate_ok(monkeypatch):
    singleton, breakers = _pre_cycle_breakers("Demasiadas pérdidas consecutivas: 5")
    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: breakers)
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=None)
    )

    result = tt.execute_trading_cycle()

    assert result["status"] == "error"
    breakers.deactivate_breaker.assert_not_called()


def test_execute_trading_cycle_clears_stale_net_si_after_validate_ok(monkeypatch):
    singleton, breakers = _pre_cycle_breakers("binance_net_fail")
    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: breakers)
    monkeypatch.setattr(
        tt, "create_optimized_grid_manager", AsyncMock(return_value=None)
    )

    result = tt.execute_trading_cycle()

    assert result["status"] == "error"
    breakers.deactivate_breaker.assert_called_once_with("system_integrity")
