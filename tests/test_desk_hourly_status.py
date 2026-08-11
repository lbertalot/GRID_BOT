"""TDD — desk hourly status (paper window digest)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.desk_hourly_status import (
    STATUS_AT,
    STATUS_OFF,
    STATUS_ON,
    collect_desk_digest,
    merge_global_status,
    render_day2_action_plan,
    window_day_number,
    write_day2_action_plan,
)
from app.core.desk_area_actions import format_actions_telegram, plan_actions_for_areas

HASH = "630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f"


def _sample(*, at: str, equity: str = "1000", daily_close=None):
    return {
        "at": at,
        "equity": equity,
        "cash": equity,
        "inventory_value": "0",
        "deployed_capital": "200",
        "config_hash": HASH,
        "daily_close_at": daily_close,
    }


def test_window_day_number_anchor():
    when = datetime(2026, 8, 6, 15, 0, tzinfo=timezone.utc)
    assert window_day_number(when, anchor_date="2026-08-06") == 1
    when2 = datetime(2026, 8, 7, 1, 0, tzinfo=timezone.utc)
    assert window_day_number(when2, anchor_date="2026-08-06") == 2


def test_merge_global_status_worst_wins():
    assert merge_global_status([STATUS_ON, "AT_RISK"]) == "AT_RISK"
    assert merge_global_status([STATUS_ON, STATUS_OFF, "AT_RISK"]) == STATUS_OFF
    assert merge_global_status([STATUS_ON, STATUS_ON]) == STATUS_ON


def test_collect_on_track_paper_fresh_sample():
    now = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    samples = [
        _sample(
            at="2026-08-06T00:00:00+00:00",
            daily_close="2026-08-06T00:00:00+00:00",
        ),
        _sample(at="2026-08-06T11:30:00+00:00"),
    ]
    d = collect_desk_digest(
        when=now,
        series_samples=samples,
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    assert d.day_n == 1
    assert d.effective_mode == "paper"
    assert d.equity_last == "1000"
    by = {a.code: a for a in d.areas}
    assert by["SEC"].status == STATUS_ON
    assert by["MM"].status == STATUS_ON
    assert by["BE"].status == STATUS_ON
    assert "Pase a Live: ❌ NO" in d.ceo_digest_text()
    assert "Reporte CEO" in d.full_telegram_payload()
    assert "Equity Actual:" in d.ceo_digest_text()


def test_ceo_message_at_risk_format():
    now = datetime(2026, 8, 6, 11, 5, tzinfo=timezone.utc)
    samples = [
        _sample(
            at="2026-08-06T00:00:00+00:00",
            daily_close="2026-08-06T00:00:00+00:00",
        ),
        _sample(at="2026-08-06T11:00:00+00:00"),
    ]
    d = collect_desk_digest(
        when=now,
        series_samples=samples,
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=True,
        expected_hash=HASH,
    )
    text = d.ceo_digest_text()
    assert "Reporte CEO | Día 1/30 (11:05Z)" in text
    assert "Modo: Paper Trading | Pase a Live: ❌ NO" in text
    assert "Equity Actual: 1000" in text
    assert "Variación: 0.00%" in text
    assert "EN RIESGO (AT_RISK)" in text
    assert "RISK" in text
    assert "breakers" in text.lower() or "breaker" in text.lower()
    assert "Resto de las áreas (ON TRACK)" in text or "ON TRACK" in text
    assert "Backend registró" in text
    assert "cierres diarios" in text
    assert "PROMOTE_LIVE" not in text or "❌ NO" in text


def test_collect_off_track_force_real():
    now = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    d = collect_desk_digest(
        when=now,
        series_samples=[_sample(at="2026-08-06T11:50:00+00:00")],
        trading_snapshot={
            "effective_mode": "real_armed",
            "force_real_mode": True,
            "trading_enabled": True,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    assert d.global_status == STATUS_OFF
    by = {a.code: a for a in d.areas}
    assert by["SEC"].status == STATUS_OFF


def test_collect_hash_drift_off():
    now = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    bad = _sample(at="2026-08-06T11:50:00+00:00")
    bad["config_hash"] = "deadbeef" * 8
    d = collect_desk_digest(
        when=now,
        series_samples=[bad],
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    by = {a.code: a for a in d.areas}
    assert by["MM"].status == STATUS_OFF
    assert d.global_status == STATUS_OFF


def test_gap_over_two_hours_off():
    now = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    d = collect_desk_digest(
        when=now,
        series_samples=[_sample(at="2026-08-06T08:00:00+00:00")],
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    by = {a.code: a for a in d.areas}
    assert by["BE"].status == STATUS_OFF


def test_day2_action_plan_no_promote_live(tmp_path: Path):
    now = datetime(2026, 8, 6, 23, 50, tzinfo=timezone.utc)
    d = collect_desk_digest(
        when=now,
        series_samples=[
            _sample(
                at="2026-08-06T23:40:00+00:00",
                daily_close="2026-08-07T00:00:00+00:00",
            )
        ],
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    md = render_day2_action_plan(d)
    assert "PROMOTE_LIVE" in md and "NO" in md
    assert "Día 2" in md
    path = write_day2_action_plan(d, root=tmp_path)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "PROMOTE_LIVE" in text
    assert "NO" in text


def test_telegram_payload_truncates_under_limit():
    now = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    d = collect_desk_digest(
        when=now,
        series_samples=[_sample(at="2026-08-06T11:55:00+00:00")],
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    assert len(d.full_telegram_payload()) <= 4096


def test_equity_dd_at_risk_triggers_mm_quant_and_actions():
    """CEO 2026-08-10: ΔE₀ ≤ −1.5% → AT_RISK QUANT+MM + DESK AUTO ACCIONES."""
    now = datetime(2026, 8, 10, 18, 5, tzinfo=timezone.utc)
    samples = [
        _sample(
            at="2026-08-10T00:00:00+00:00",
            equity="1000",
            daily_close="2026-08-10T00:00:00+00:00",
        ),
        _sample(at="2026-08-10T18:00:00+00:00", equity="984"),  # −1.6%
    ]
    d = collect_desk_digest(
        when=now,
        series_samples=samples,
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    by = {a.code: a for a in d.areas}
    assert d.global_status == STATUS_AT
    assert by["MM"].status == STATUS_AT
    assert by["QUANT"].status == STATUS_AT
    assert "ΔE0" in by["MM"].deviation or "E0" in by["MM"].deviation
    assert "EN RIESGO (AT_RISK)" in d.ceo_digest_text()
    actions = plan_actions_for_areas(d.areas)
    codes = {a.code for a in actions}
    assert "MM" in codes and "QUANT" in codes
    assert any("PnL" in a.action or "tear" in a.action.lower() for a in actions)


def test_equity_dd_off_track_at_minus_3_pct():
    """CEO 2026-08-10: ΔE₀ ≤ −3% → OFF_TRACK QUANT+MM."""
    now = datetime(2026, 8, 10, 18, 5, tzinfo=timezone.utc)
    samples = [
        _sample(
            at="2026-08-10T00:00:00+00:00",
            equity="1000",
            daily_close="2026-08-10T00:00:00+00:00",
        ),
        _sample(at="2026-08-10T18:00:00+00:00", equity="970"),  # −3.0%
    ]
    d = collect_desk_digest(
        when=now,
        series_samples=samples,
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    by = {a.code: a for a in d.areas}
    assert d.global_status == STATUS_OFF
    assert by["MM"].status == STATUS_OFF
    assert by["QUANT"].status == STATUS_OFF
    assert "FUERA DE CURSO (OFF_TRACK)" in d.ceo_digest_text()


def test_equity_dd_below_threshold_stays_on_track():
    now = datetime(2026, 8, 10, 12, 5, tzinfo=timezone.utc)
    samples = [
        _sample(
            at="2026-08-10T00:00:00+00:00",
            equity="1000",
            daily_close="2026-08-10T00:00:00+00:00",
        ),
        _sample(at="2026-08-10T12:00:00+00:00", equity="990"),  # −1.0%
    ]
    d = collect_desk_digest(
        when=now,
        series_samples=samples,
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    by = {a.code: a for a in d.areas}
    assert d.global_status == STATUS_ON
    assert by["MM"].status == STATUS_ON
    assert by["QUANT"].status == STATUS_ON
    assert plan_actions_for_areas(d.areas) == []


def test_equity_dd_pause_gate_at_minus_5_pct():
    """Desk Día 7: ΔE₀ ≤ −5% → OFF + ACCIONES pausa (no auto emergency_stop)."""
    from app.core.desk_hourly_status import equity_dd_pause_recommended

    now = datetime(2026, 8, 11, 12, 5, tzinfo=timezone.utc)
    samples = [
        _sample(
            at="2026-08-11T00:00:00+00:00",
            equity="1000",
            daily_close="2026-08-11T00:00:00+00:00",
        ),
        _sample(at="2026-08-11T12:00:00+00:00", equity="950"),  # −5.0%
    ]
    assert equity_dd_pause_recommended("-5.0%") is True
    assert equity_dd_pause_recommended("-2.5%") is False
    d = collect_desk_digest(
        when=now,
        series_samples=samples,
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=False,
        expected_hash=HASH,
    )
    by = {a.code: a for a in d.areas}
    assert d.global_status == STATUS_OFF
    assert by["MM"].status == STATUS_OFF
    assert by["QUANT"].status == STATUS_OFF
    assert by["RISK"].status == STATUS_OFF
    assert any("PAUSE_GATE" in n for n in d.notes)
    assert "EMERGENCY_STOP" in by["MM"].next_60m
    actions = plan_actions_for_areas(d.areas)
    assert any("EMERGENCY_STOP" in a.action for a in actions)
    assert "PROMOTE_LIVE: NO" in (format_actions_telegram(actions) or "")
    # No auto-flip de flags live/emergency en el digest
    assert d.effective_mode == "paper"


def test_equity_dd_at_risk_does_not_false_positive_pause_actions():
    """Legend gate_pausa= no debe disparar ACCIONES de PAUSE_GATE."""
    now = datetime(2026, 8, 11, 1, 14, tzinfo=timezone.utc)
    samples = [
        _sample(
            at="2026-08-11T00:00:00+00:00",
            equity="1000",
            daily_close="2026-08-11T00:00:00+00:00",
        ),
        _sample(at="2026-08-11T01:00:00+00:00", equity="976.16"),  # −2.384%
    ]
    d = collect_desk_digest(
        when=now,
        series_samples=samples,
        trading_snapshot={
            "effective_mode": "paper",
            "force_real_mode": False,
            "trading_enabled": False,
        },
        any_open_breakers=True,
        expected_hash=HASH,
    )
    by = {a.code: a for a in d.areas}
    assert d.global_status == STATUS_AT
    assert by["MM"].status == STATUS_AT
    assert "PAUSE_GATE" not in by["MM"].deviation
    assert "gate_pausa=" in by["MM"].deviation
    assert d.notes == []
    actions = plan_actions_for_areas(d.areas)
    assert not any("EMERGENCY_STOP" in a.action for a in actions)
