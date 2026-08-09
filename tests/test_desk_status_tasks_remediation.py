"""Unit — desk_status_tasks auto-remediation wiring (no Celery/network). COV-1.3."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def digest_stub():
    d = SimpleNamespace(
        day_n=3,
        global_status="AT_RISK",
        effective_mode="paper",
        equity_last="1000.00",
    )
    d.full_telegram_payload = MagicMock(return_value="DIGEST PAYLOAD")
    return d


def test_hourly_digest_disabled(paper_env):
    from app.services import desk_status_tasks as mod

    with patch.object(mod, "_run_auto_remediation") as rem:
        with patch("app.core.desk_hourly_status.is_enabled", return_value=False):
            out = mod.send_desk_hourly_digest()
    assert out == {"ok": False, "reason": "disabled"}
    rem.assert_not_called()


def test_hourly_digest_sends_remediation_telegram(paper_env, digest_stub):
    from app.services import desk_status_tasks as mod

    rem_result = {
        "acted": True,
        "action": "reset_system_integrity",
        "reason": "stale_after_validate_ok",
        "breaker_reason_before": "binance_net_fail",
        "active_breakers_after": [],
    }
    with (
        patch("app.core.desk_hourly_status.is_enabled", return_value=True),
        patch(
            "app.core.desk_hourly_status.build_live_digest",
            return_value=digest_stub,
        ),
        patch(
            "app.core.desk_auto_remediation.maybe_remediate_stale_system_integrity",
            return_value=rem_result,
        ),
        patch.object(mod, "_telegram", return_value=True) as tg,
    ):
        out = mod.send_desk_hourly_digest()

    assert out["ok"] is True
    assert out["remediation"]["acted"] is True
    assert tg.call_count == 2
    assert any("REMEDIADO" in str(c.args[0]) for c in tg.call_args_list)


def test_run_auto_remediation_swallows_errors(paper_env):
    from app.services import desk_status_tasks as mod

    with patch(
        "app.core.desk_auto_remediation.maybe_remediate_stale_system_integrity",
        side_effect=RuntimeError("explode"),
    ):
        out = mod._run_auto_remediation()
    assert out == {
        "acted": False,
        "action": "error",
        "reason": "explode",
    }


def test_eod_includes_remediation_fields(paper_env, digest_stub):
    from app.services import desk_status_tasks as mod

    rem_result = {
        "acted": False,
        "action": "hold",
        "reason": "validate_not_ok",
        "validate": {"auth_ok": False, "net_ok": True},
    }
    with (
        patch("app.core.desk_hourly_status.is_enabled", return_value=True),
        patch(
            "app.core.desk_hourly_status.build_live_digest",
            return_value=digest_stub,
        ),
        patch(
            "app.core.desk_hourly_status.write_day2_action_plan",
            return_value=Path("/tmp/day2.md"),
        ),
        patch(
            "app.core.desk_auto_remediation.maybe_remediate_stale_system_integrity",
            return_value=rem_result,
        ),
        patch.object(mod, "_telegram", return_value=True) as tg,
    ):
        out = mod.send_desk_eod_day_plan()

    assert out["ok"] is True
    assert out["remediation"]["action"] == "hold"
    assert out["path"] == "/tmp/day2.md"
    assert tg.call_count == 2
    assert "Auto-remediate" in tg.call_args_list[-1].args[0]
    assert "hold" in tg.call_args_list[-1].args[0]


def test_eod_disabled(paper_env):
    from app.services import desk_status_tasks as mod

    with patch("app.core.desk_hourly_status.is_enabled", return_value=False):
        assert mod.send_desk_eod_day_plan() == {
            "ok": False,
            "reason": "disabled",
        }


def test_telegram_wrapper_calls_alert(paper_env):
    from app.services import desk_status_tasks as mod

    with patch(
        "app.services.telegram_alert.send_telegram_alert",
        return_value=True,
    ) as send:
        assert mod._telegram("hi") is True
    send.assert_called_once_with("hi")
