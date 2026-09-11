"""Override RCA / prueba SI: idle 12h·720 ticks y techo 96h·5760 ticks.

Paper-only. No toca live. Redis se fuerza a fallar → fallback in-process.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.breaker_override import (
    TRIAL_MAX_AGE_HOURS,
    TRIAL_MAX_AGE_TICKS,
    TRIAL_MAX_IDLE_HOURS,
    TRIAL_MAX_IDLE_TICKS,
    OverrideCheckResult,
    _MemoryFallback,
    _save,
    check_and_consume_override,
    get_override,
    grant_override,
)


@pytest.fixture
def memory_override(monkeypatch):
    _MemoryFallback._store.clear()

    def _boom():
        raise RuntimeError("redis disabled in unit test")

    monkeypatch.setattr("app.core.breaker_override._redis", _boom)
    yield
    _MemoryFallback._store.clear()


def test_trial_constants_cerradas():
    assert TRIAL_MAX_IDLE_HOURS == 12
    assert TRIAL_MAX_IDLE_TICKS == 720
    assert TRIAL_MAX_AGE_HOURS == 96
    assert TRIAL_MAX_AGE_TICKS == 5760


def test_grant_trial_fija_constantes_no_flags(memory_override):
    t0 = datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    ov = grant_override(
        "system_integrity",
        granted_by="Desk Lead",
        rca_ref="Docs/ops/trial-si-5x15-2026-08-29.md",
        ledger_watermark=t0,
        trial=True,
    )
    assert ov.max_ticks == TRIAL_MAX_IDLE_TICKS
    assert ov.max_idle_hours == TRIAL_MAX_IDLE_HOURS
    assert ov.max_age_hours == TRIAL_MAX_AGE_HOURS
    assert ov.max_age_ticks == TRIAL_MAX_AGE_TICKS
    assert ov.ledger_watermark == t0.isoformat()


def test_primer_close_post_watermark_limpia_y_no_skipea(memory_override):
    t0 = datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    grant_override(
        "system_integrity",
        granted_by="Desk Lead",
        rca_ref="trial",
        ledger_watermark=t0,
        trial=True,
    )
    result = check_and_consume_override(
        "system_integrity",
        ledger_latest_closed_at=t0 + timedelta(hours=1),
    )
    assert isinstance(result, OverrideCheckResult)
    assert result.skip_activation is False
    assert result.force_reduce_only is False
    assert check_and_consume_override("system_integrity").override is None


def test_idle_ticks_sin_close_post_t0_fuerza_reduce_only(memory_override):
    t0 = datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    grant_override(
        "system_integrity",
        granted_by="Desk Lead",
        rca_ref="trial",
        ledger_watermark=t0,
        trial=True,
    )
    now = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    ov = get_override("system_integrity")
    assert ov is not None
    ov.granted_at = (now - timedelta(minutes=5)).isoformat()
    _save(ov)
    last = None
    for _ in range(TRIAL_MAX_IDLE_TICKS):
        last = check_and_consume_override(
            "system_integrity",
            ledger_latest_closed_at=t0,
            now=now,
        )
        assert last.skip_activation is True
        assert last.force_reduce_only is False
    expired = check_and_consume_override(
        "system_integrity",
        ledger_latest_closed_at=t0,
        now=now,
    )
    assert expired.skip_activation is False
    assert expired.force_reduce_only is True
    assert check_and_consume_override("system_integrity").override is None


def _backdate(hours: float) -> datetime:
    granted = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)
    ov = get_override("system_integrity")
    assert ov is not None
    ov.granted_at = granted.isoformat()
    _save(ov)
    return granted + timedelta(hours=hours)


def test_idle_12h_de_reloj_sin_close_fuerza_reduce_only(memory_override):
    t0 = datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    grant_override(
        "system_integrity",
        granted_by="Desk Lead",
        rca_ref="trial",
        ledger_watermark=t0,
        trial=True,
    )
    later = _backdate(12)
    result = check_and_consume_override(
        "system_integrity",
        ledger_latest_closed_at=t0,
        now=later,
    )
    assert result.force_reduce_only is True
    assert result.skip_activation is False


def test_techo_96h_fuerza_reduce_only_aunque_queden_ticks_idle(memory_override):
    t0 = datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    grant_override(
        "system_integrity",
        granted_by="Desk Lead",
        rca_ref="trial",
        ledger_watermark=t0,
        trial=True,
    )
    later = _backdate(96)
    result = check_and_consume_override(
        "system_integrity",
        ledger_latest_closed_at=t0,
        now=later,
    )
    assert result.force_reduce_only is True


def test_legacy_max_ticks_10_no_fuerza_reduce_only(memory_override):
    t0 = datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    grant_override(
        "system_integrity",
        granted_by="Desk Lead",
        rca_ref="rca-legacy",
        ledger_watermark=t0,
        max_ticks=10,
    )
    now = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    ov = get_override("system_integrity")
    assert ov is not None
    ov.granted_at = (now - timedelta(minutes=5)).isoformat()
    _save(ov)
    for _ in range(10):
        check_and_consume_override(
            "system_integrity",
            ledger_latest_closed_at=t0,
            now=now,
        )
    expired = check_and_consume_override(
        "system_integrity",
        ledger_latest_closed_at=t0,
        now=now,
    )
    assert expired.skip_activation is False
    assert expired.force_reduce_only is False
