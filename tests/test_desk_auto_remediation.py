"""TDD — desk auto-remediation paper (stale system_integrity). COV-1.3."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# paper_env / mock_binance from tests/fixtures/paper_cov via conftest


def _si_breakers(reason: str = "binance_net_fail", active: bool = True):
    return {
        "active_breakers": ["system_integrity"] if active else [],
        "breakers": {
            "system_integrity": {"active": active, "reason": reason},
        },
    }


def _paper_sot(monkeypatch):
    monkeypatch.setattr(
        "app.core.desk_auto_remediation._is_paper_sot",
        lambda: True,
    )


def _ck(monkeypatch, *, after=None, deactivate=None):
    mock_ck = MagicMock()
    mock_ck.get_all_breakers_status.return_value = after or {
        "active_breakers": []
    }
    if deactivate is not None:
        mock_ck.deactivate_breaker = deactivate
    monkeypatch.setattr(
        "app.core.circuit_breakers.get_shared_breakers",
        lambda: mock_ck,
    )
    return mock_ck


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("false", False),
        ("0", False),
        ("no", False),
        ("true", True),
        ("1", True),
        ("YES", True),
        ("On", True),
        ("  true  ", True),
    ],
)
def test_auto_remediate_enabled_env_variants(paper_env, monkeypatch, raw, expected):
    monkeypatch.setenv("DESK_AUTO_REMEDIATE_BREAKERS", raw)
    from app.core.desk_auto_remediation import auto_remediate_enabled

    assert auto_remediate_enabled() is expected


def test_skip_when_disabled(paper_env, monkeypatch):
    monkeypatch.setenv("DESK_AUTO_REMEDIATE_BREAKERS", "false")
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers(),
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["acted"] is False and r["action"] == "skipped"


def test_skip_when_not_paper_sot(paper_env, monkeypatch):
    monkeypatch.setattr(
        "app.core.desk_auto_remediation._is_paper_sot",
        lambda: False,
    )
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers(),
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["action"] == "skipped" and r["reason"] == "not_paper_sot"


def test_none_when_system_integrity_closed(paper_env, monkeypatch):
    _paper_sot(monkeypatch)
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers={"active_breakers": [], "breakers": {}},
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["action"] == "none" and r["reason"] == "system_integrity_closed"


def test_hold_when_validate_fails(paper_env, monkeypatch):
    _paper_sot(monkeypatch)
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers(),
        validate={"auth_ok": False, "net_ok": True},
    )
    assert r["action"] == "hold" and r["reason"] == "validate_not_ok"


def test_reset_async_deactivate(paper_env, monkeypatch):
    _paper_sot(monkeypatch)

    async def _deact(name):
        assert name == "system_integrity"

    _ck(monkeypatch, deactivate=_deact)
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers("binance_net_fail"),
        validate={"auth_ok": True, "net_ok": True, "ok": True},
    )
    assert r["acted"] is True and r["action"] == "reset_system_integrity"


def test_refuse_unknown_or_pnl_reason_even_if_validate_ok(paper_env, monkeypatch):
    """CEO/ops 2026-08-10: no borrar 'pérdidas consecutivas' por auth/net OK."""
    _paper_sot(monkeypatch)
    mock_ck = _ck(monkeypatch, deactivate=MagicMock())
    from app.core.desk_auto_remediation import (
        format_remediation_telegram,
        maybe_remediate_stale_system_integrity,
    )

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers("Demasiadas pérdidas consecutivas: 5"),
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["acted"] is False
    assert r["action"] == "hold_trading_reason"
    assert "consecutivas" in (r.get("breaker_reason") or "").lower()
    mock_ck.deactivate_breaker.assert_not_called()
    msg = format_remediation_telegram(r)
    assert msg is None  # CEO plain: heartbeat vía breaker_ceo_watch
    from app.core.breaker_ceo_watch import process_si_ceo_watch

    watch = process_si_ceo_watch(
        si_open=True,
        reason=r.get("breaker_reason"),
        now=9_000_000.0,
    )
    assert watch and "Dinero real: NO" in watch
    assert "no resetear" in watch.lower()
    assert "estabilice" not in watch.lower()
    assert "robo" not in watch.lower()
    assert "breaker_type: system_integrity" in watch
    assert "override" not in watch.lower()


def test_refuse_empty_reason(paper_env, monkeypatch):
    _paper_sot(monkeypatch)
    mock_ck = _ck(monkeypatch, deactivate=MagicMock())
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers(""),
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["acted"] is False and r["action"] == "hold_trading_reason"
    mock_ck.deactivate_breaker.assert_not_called()


def test_reset_sync_binance_auth_fail(paper_env, monkeypatch):
    _paper_sot(monkeypatch)
    mock_ck = _ck(monkeypatch, deactivate=MagicMock())
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers("binance_auth_fail"),
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["acted"] is True
    mock_ck.deactivate_breaker.assert_called_once_with("system_integrity")


def test_error_when_deactivate_missing(paper_env, monkeypatch):
    _paper_sot(monkeypatch)
    monkeypatch.setattr(
        "app.core.circuit_breakers.get_shared_breakers",
        lambda: MagicMock(spec=[]),
    )
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers(),
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["action"] == "error" and r["reason"] == "no_deactivate"


def test_error_when_deactivate_raises(paper_env, monkeypatch):
    _paper_sot(monkeypatch)
    _ck(monkeypatch, deactivate=MagicMock(side_effect=RuntimeError("boom")))
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers(),
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["action"] == "error" and "boom" in r["reason"]


def test_acted_false_when_still_open_after_reset(paper_env, monkeypatch):
    _paper_sot(monkeypatch)
    _ck(
        monkeypatch,
        after={"active_breakers": ["system_integrity"]},
        deactivate=MagicMock(),
    )
    from app.core.desk_auto_remediation import maybe_remediate_stale_system_integrity

    r = maybe_remediate_stale_system_integrity(
        breakers=_si_breakers(),
        validate={"auth_ok": True, "net_ok": True},
    )
    assert r["acted"] is False and r["action"] == "reset_system_integrity"


def test_is_paper_sot_ledger_and_fallback(paper_env, monkeypatch):
    from app.core import desk_auto_remediation as mod

    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ):
        assert mod._is_paper_sot() is True
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        side_effect=ImportError("no ledger"),
    ):
        monkeypatch.setenv("PAPER_TRADING", "true")
        assert mod._is_paper_sot() is True
        monkeypatch.setenv("PAPER_TRADING", "false")
        assert mod._is_paper_sot() is False


def test_validate_and_breaker_snapshot_helpers(paper_env, monkeypatch, mock_binance):
    mock_binance.validate_credentials_and_connectivity.return_value = {
        "auth_ok": True,
        "net_ok": True,
    }
    from app.core import desk_auto_remediation as mod

    assert mod._validate_binance()["auth_ok"] is True
    _ck(monkeypatch, after={"active_breakers": ["x"]})
    assert mod._breaker_snapshot()["active_breakers"] == ["x"]
    monkeypatch.setattr(
        "app.core.circuit_breakers.get_shared_breakers",
        lambda: MagicMock(spec=[]),
    )
    assert mod._breaker_snapshot() == {}


@pytest.mark.parametrize(
    "payload,needle",
    [
        (
            {
                "acted": True,
                "breaker_reason_before": "binance_net_fail",
                "active_breakers_after": [],
            },
            "Freno de conexión",
        ),
        (
            {
                "acted": False,
                "action": "hold",
                "validate": {"auth_ok": False, "net_ok": True},
            },
            "Freno: no valida",
        ),
        ({"acted": False, "action": "none"}, None),
    ],
)
def test_format_remediation_telegram(payload, needle):
    from app.core.desk_auto_remediation import format_remediation_telegram

    msg = format_remediation_telegram(payload)
    if needle is None:
        assert msg is None
    else:
        assert msg and needle in msg and "Dinero real: NO" in msg
