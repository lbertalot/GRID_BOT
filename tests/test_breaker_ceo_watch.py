"""TDD — watch CEO system_integrity (heartbeat 6h + clear instantáneo)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.breaker_ceo_watch import process_si_ceo_watch
from app.core.telegram_ceo_copy import HOLD_PNL_MIN_REPEAT_S, reset_debounce_memory

NO_GO_REASON = (
    "Override de prueba SI expiró sin close post-t0 "
    "(latest_closed_at=2026-08-26T15:45:37.370240+00:00); "
    "system_integrity REDUCE_ONLY (NO-GO prueba)"
)


@pytest.fixture(autouse=True)
def _isolate():
    with patch("app.core.telegram_ceo_copy._redis_client", return_value=None):
        reset_debounce_memory()
        yield
        reset_debounce_memory()


def test_hold_si_heartbeat_every_6h_not_hourly():
    assert HOLD_PNL_MIN_REPEAT_S == 6 * 3600
    t0 = 1_000_000.0
    first = process_si_ceo_watch(
        si_open=True,
        reason=NO_GO_REASON,
        operational_state="REDUCE_ONLY",
        activated_at="2026-09-10T07:13:22.645098",
        historical_streak=19,
        now=t0,
    )
    assert first is not None
    assert "breaker_type: system_integrity" in first
    assert "NO-GO SI: 0 cierres post-t0; idle vencido" in first
    assert "Racha histórica preservada: 19; no implica una pérdida nueva" in first
    assert "Modo: PAPER" in first
    assert "Dinero real: NO" in first
    assert "cada hora" not in first.lower()
    assert process_si_ceo_watch(
        si_open=True,
        reason=NO_GO_REASON,
        operational_state="REDUCE_ONLY",
        activated_at="2026-09-10T07:13:22.645098",
        historical_streak=19,
        now=t0 + 3600,
    ) is None
    again = process_si_ceo_watch(
        si_open=True,
        reason=NO_GO_REASON,
        operational_state="REDUCE_ONLY",
        activated_at="2026-09-10T07:13:22.645098",
        historical_streak=19,
        now=t0 + HOLD_PNL_MIN_REPEAT_S,
    )
    assert again is not None
    assert "NO-GO SI" in again


def test_hold_emits_immediately_on_state_fingerprint_change():
    t0 = 1_500_000.0
    first = process_si_ceo_watch(
        si_open=True,
        reason=NO_GO_REASON,
        operational_state="REDUCE_ONLY",
        activated_at="2026-09-10T07:13:22Z",
        historical_streak=19,
        now=t0,
    )
    assert first is not None
    changed = process_si_ceo_watch(
        si_open=True,
        reason="Demasiadas pérdidas consecutivas: 19",
        operational_state="REDUCE_ONLY",
        activated_at="2026-09-10T07:13:22Z",
        historical_streak=19,
        now=t0 + 60,
    )
    assert changed is not None
    assert "breaker_type: system_integrity" in changed


def test_cleared_message_instant_on_open_to_closed_transition():
    t0 = 2_000_000.0
    opened = process_si_ceo_watch(
        si_open=True,
        reason="Demasiadas pérdidas consecutivas: 5",
        historical_streak=5,
        now=t0,
    )
    assert opened is not None
    cleared = process_si_ceo_watch(si_open=False, reason="", now=t0 + 30)
    assert cleared is not None
    assert "levantado" in cleared.lower()
    assert "Modo: PAPER" in cleared
    assert "Dinero real: NO" in cleared
    assert process_si_ceo_watch(si_open=False, reason="", now=t0 + 60) is None


def test_cleared_not_emitted_on_closed_snapshot_without_prior_open():
    t0 = 2_100_000.0
    assert process_si_ceo_watch(si_open=False, reason="", now=t0) is None
    assert process_si_ceo_watch(si_open=False, reason="", now=t0 + 30) is None


def test_skip_cleared_when_auth_remediated():
    t0 = 3_000_000.0
    from app.core.telegram_ceo_copy import _save_last
    from app.core.breaker_ceo_watch import SI_STATE_CHANNEL

    _save_last(SI_STATE_CHANNEL, "open|auth|binance_auth_fail", t0)
    assert (
        process_si_ceo_watch(si_open=False, reason="", skip_cleared=True, now=t0 + 1)
        is None
    )


def test_auth_open_does_not_emit_hold_pnl_here():
    msg = process_si_ceo_watch(
        si_open=True,
        reason="binance_auth_fail",
        now=4_000_000.0,
    )
    assert msg is None


def test_normalize_active_closed_is_open_not_contradictory():
    from app.core.breaker_ceo_watch import normalize_si_public_snapshot

    snap = normalize_si_public_snapshot(
        active=True,
        in_active_breakers=True,
        operational_state="CLOSED",
        reason=NO_GO_REASON,
        activated_at="2026-09-10T07:13:22.645098",
    )
    assert snap.active is True
    assert snap.public_state == "OPEN"
    assert "CLOSED" not in snap.public_state
    assert snap.ops_inconsistent is True
    assert snap.activated_at.startswith("2026-09-10")
    assert "system_integrity" in snap.fingerprint
    assert snap.reason_kind == "trial_nogo"


def test_two_partial_snapshots_same_si_emit_once():
    t0 = 5_000_000.0
    first = process_si_ceo_watch(
        si_open=True,
        reason=NO_GO_REASON,
        historical_streak=19,
        now=t0,
    )
    assert first is not None
    assert "Estado: OPEN" in first
    assert "OPEN · CLOSED" not in first
    second = process_si_ceo_watch(
        si_open=True,
        reason=NO_GO_REASON,
        operational_state="CLOSED",
        activated_at="2026-09-10T07:13:22.645098",
        historical_streak=19,
        now=t0 + 60,
    )
    assert second is None


def test_active_closed_copy_never_says_open_closed():
    msg = process_si_ceo_watch(
        si_open=True,
        reason=NO_GO_REASON,
        operational_state="CLOSED",
        activated_at="2026-09-10T07:13:22.645098",
        historical_streak=19,
        now=6_000_000.0,
    )
    assert msg is not None
    assert "OPEN · CLOSED" not in msg
    assert "Estado: OPEN" in msg
    assert "Desde: n/d" not in msg
    assert "2026-09-10T07:13:22" in msg
    assert "pérdida nueva" in msg.lower()
    assert "varios cierres seguidos" not in msg.lower()
    low = msg.lower()
    assert "override" not in low
    assert "wipe" not in low
    assert "live" not in low or "dinero real: no" in low


def test_missing_activated_at_does_not_reset_6h_cadence():
    t0 = 7_000_000.0
    first = process_si_ceo_watch(
        si_open=True,
        reason=NO_GO_REASON,
        operational_state="REDUCE_ONLY",
        activated_at="2026-09-10T07:13:22Z",
        historical_streak=19,
        now=t0,
    )
    assert first is not None
    assert (
        process_si_ceo_watch(
            si_open=True,
            reason=NO_GO_REASON,
            operational_state="REDUCE_ONLY",
            activated_at="",
            historical_streak=19,
            now=t0 + 3600,
        )
        is None
    )
    again = process_si_ceo_watch(
        si_open=True,
        reason=NO_GO_REASON,
        operational_state="REDUCE_ONLY",
        activated_at="",
        historical_streak=19,
        now=t0 + HOLD_PNL_MIN_REPEAT_S,
    )
    assert again is not None
    assert "Desde: n/d" not in again
