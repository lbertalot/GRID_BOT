"""TDD — desk auto-remediation paper (stale system_integrity)."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def paper_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("DESK_AUTO_REMEDIATE_BREAKERS", "true")


def test_skip_when_disabled(paper_env, monkeypatch):
    monkeypatch.setenv("DESK_AUTO_REMEDIATE_BREAKERS", "false")
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers={"active_breakers": ["system_integrity"]},
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["acted"] is False
    assert r["action"] == "skipped"


def test_hold_when_validate_fails(paper_env, monkeypatch):
    monkeypatch.setattr(
        "app.core.desk_auto_remediation._is_paper_sot",
        lambda: True,
    )
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers={
            "active_breakers": ["system_integrity"],
            "breakers": {
                "system_integrity": {
                    "active": True,
                    "reason": "binance_net_fail",
                }
            },
        },
        validate={"auth_ok": False, "net_ok": True},
    )
    assert r["acted"] is False
    assert r["action"] == "hold"


def test_reset_when_stale_and_validate_ok(paper_env, monkeypatch):
    monkeypatch.setattr(
        "app.core.desk_auto_remediation._is_paper_sot",
        lambda: True,
    )
    mock_ck = MagicMock()
    mock_ck.get_all_breakers_status.return_value = {"active_breakers": []}

    async def _deact(name):
        assert name == "system_integrity"

    mock_ck.deactivate_breaker = _deact
    monkeypatch.setattr(
        "app.core.circuit_breakers.get_shared_breakers",
        lambda: mock_ck,
    )
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers={
            "active_breakers": ["system_integrity"],
            "breakers": {
                "system_integrity": {
                    "active": True,
                    "reason": "binance_net_fail",
                }
            },
        },
        validate={"auth_ok": True, "net_ok": True, "ok": True},
    )
    assert r["acted"] is True
    assert r["action"] == "reset_system_integrity"


def test_format_telegram_acted():
    from app.core.desk_auto_remediation import format_remediation_telegram

    msg = format_remediation_telegram(
        {
            "acted": True,
            "breaker_reason_before": "binance_net_fail",
            "active_breakers_after": [],
        }
    )
    assert msg and "REMEDIADO" in msg and "PROMOTE_LIVE: NO" in msg


def test_format_telegram_hold():
    from app.core.desk_auto_remediation import format_remediation_telegram

    msg = format_remediation_telegram(
        {
            "acted": False,
            "action": "hold",
            "validate": {"auth_ok": False, "net_ok": True},
        }
    )
    assert msg and "HOLD" in msg
