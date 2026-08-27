"""TDD — watch CEO system_integrity (heartbeat 1h + clear instantáneo)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.breaker_ceo_watch import process_si_ceo_watch
from app.core.telegram_ceo_copy import HOLD_PNL_MIN_REPEAT_S, reset_debounce_memory


@pytest.fixture(autouse=True)
def _isolate():
    with patch("app.core.telegram_ceo_copy._redis_client", return_value=None):
        reset_debounce_memory()
        yield
        reset_debounce_memory()


def test_hold_pnl_heartbeat_every_hour():
    assert HOLD_PNL_MIN_REPEAT_S == 3600
    t0 = 1_000_000.0
    first = process_si_ceo_watch(
        si_open=True,
        reason="Demasiadas pérdidas consecutivas: 19",
        now=t0,
    )
    assert first is not None
    assert "Desk Lead" in first
    assert "cada hora" in first.lower()
    assert process_si_ceo_watch(
        si_open=True,
        reason="Demasiadas pérdidas consecutivas: 19",
        now=t0 + 600,
    ) is None
    again = process_si_ceo_watch(
        si_open=True,
        reason="Demasiadas pérdidas consecutivas: 19",
        now=t0 + HOLD_PNL_MIN_REPEAT_S,
    )
    assert again is not None
    assert "19 cierres" in again


def test_cleared_message_instant_on_close():
    t0 = 2_000_000.0
    assert process_si_ceo_watch(
        si_open=True,
        reason="Demasiadas pérdidas consecutivas: 5",
        now=t0,
    )
    cleared = process_si_ceo_watch(si_open=False, reason="", now=t0 + 30)
    assert cleared is not None
    assert "levantado" in cleared.lower()
    assert "Dinero real: NO" in cleared
    # no spam si ya estaba cerrado
    assert process_si_ceo_watch(si_open=False, reason="", now=t0 + 60) is None


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
