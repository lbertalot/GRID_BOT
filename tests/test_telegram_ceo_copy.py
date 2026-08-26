"""TDD — copy Telegram CEO (español llano) + debounce. Paper-only."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.desk_hourly_status import collect_desk_digest
from app.core.telegram_ceo_copy import (
    HOLD_PNL_MIN_REPEAT_S,
    SEMAFORO_NARANJA,
    SEMAFORO_ROJO_CAPITAL,
    SEMAFORO_ROJO_SISTEMA,
    SEMAFORO_VERDE,
    ceo_semaforo,
    digest_fingerprint,
    format_alertmanager_ceo,
    render_ceo_digest,
    render_hold_pnl_telegram,
    render_invalid_ip_telegram,
    render_remediated_telegram,
    reset_debounce_memory,
    should_emit_ceo,
)
from tests.test_desk_hourly_status import HASH, _sample


@pytest.fixture(autouse=True)
def _isolate_ceo_debounce():
    """B5: no Redis real; memoria limpia entre tests."""
    with patch("app.core.telegram_ceo_copy._redis_client", return_value=None):
        reset_debounce_memory()
        yield
        reset_debounce_memory()


def _digest(*, equity="984", breakers=False, mode="paper"):
    now = datetime(2026, 8, 12, 21, 5, tzinfo=timezone.utc)
    samples = [
        _sample(
            at="2026-08-12T00:00:00+00:00",
            equity="1000",
            daily_close="2026-08-12T00:00:00+00:00",
        ),
        _sample(at="2026-08-12T21:00:00+00:00", equity=equity),
    ]
    return collect_desk_digest(
        when=now,
        series_samples=samples,
        trading_snapshot={
            "effective_mode": mode,
            "force_real_mode": mode != "paper",
            "trading_enabled": False,
        },
        any_open_breakers=breakers,
        expected_hash=HASH,
    )


def test_ceo_digest_at_risk_has_no_jargon():
    d = _digest(equity="982")  # −1.8%
    text = d.ceo_digest_text()
    assert "Cómo va la prueba" in text
    assert "Ensayo" in text
    assert "Dinero real: **NO**" in text or "Dinero real: NO" in text
    assert "aviso" in text.lower() or "NARANJA" in text
    assert "esperá" in text.lower() or "No pases" in text or "No resetear" in text
    assert "AT_RISK" not in text
    assert "GET /api" not in text
    assert "samples=" not in text
    assert "Backend registró" not in text
    assert "ΔE0" not in text
    assert "Acción requerida" not in text
    assert "ganancia" not in text.lower() or "no ganancia" in text.lower()


def test_ceo_digest_green_says_do_nothing():
    d = _digest(equity="1000", breakers=False)
    text = d.ceo_digest_text()
    assert ceo_semaforo(d) == SEMAFORO_VERDE
    assert "VERDE" in text
    assert "No hagas nada" in text
    assert "Dinero real" in text


def test_ceo_digest_off_track_is_capital_red_not_system():
    d = _digest(equity="970")
    assert ceo_semaforo(d) == SEMAFORO_ROJO_CAPITAL
    text = d.ceo_digest_text()
    assert "ROJO CAPITAL" in text
    assert "OFF_TRACK" not in text
    assert "FUERA DE CURSO" not in text
    assert "No pases a dinero real" in text


def test_ceo_digest_not_paper_is_system_red():
    d = _digest(equity="1000", mode="real_armed")
    assert ceo_semaforo(d) == SEMAFORO_ROJO_SISTEMA
    text = render_ceo_digest(d)
    assert "ROJO SISTEMA" in text
    assert "a ciegas" in text


def test_hold_pnl_copy_does_not_promise_auto_resume():
    msg = render_hold_pnl_telegram("Demasiadas pérdidas consecutivas: 5")
    assert "no lo resetees" in msg.lower() or "No tenés que resetear" in msg
    assert "Dinero real: NO" in msg
    assert "estabilice" not in msg.lower()
    assert "se reinicia solo" not in msg.lower()
    assert "PROMOTE_LIVE" not in msg
    assert "system_integrity" not in msg


def test_remediated_is_connection_not_pnl():
    msg = render_remediated_telegram()
    assert "conexión" in msg.lower()
    assert "pérdidas" in msg.lower()
    assert "Dinero real: NO" in msg
    assert "PROMOTE_LIVE" not in msg


def test_invalid_ip_copy_has_ip_no_endpoint():
    msg = render_invalid_ip_telegram("143.105.137.24", location_restricted=False)
    assert "143.105.137.24" in msg
    assert "Binance" in msg
    assert "/ip" not in msg
    assert "endpoint" not in msg.lower()
    assert "Dinero real: NO" in msg


def test_debounce_same_fingerprint_skips_second():
    reset_debounce_memory()
    fp = "1|at|paper|pnl"
    assert should_emit_ceo("digest", fp, now=1_000.0) is True
    assert should_emit_ceo("digest", fp, now=1_000.0 + 3600) is False


def test_debounce_sends_on_fingerprint_change():
    reset_debounce_memory()
    assert should_emit_ceo("digest", "1|at|paper|none", now=1.0) is True
    assert should_emit_ceo("digest", "2|off|paper|none", now=2.0) is True


def test_debounce_force_eod_always_sends():
    reset_debounce_memory()
    fp = "1|at|paper|pnl"
    assert should_emit_ceo("digest", fp, now=1.0) is True
    assert should_emit_ceo("digest", fp, force=True, now=2.0) is True


def test_hold_pnl_repeat_after_12h():
    reset_debounce_memory()
    fp = "1|at|paper|pnl"
    assert should_emit_ceo(
        "hold_pnl", fp, min_repeat_s=HOLD_PNL_MIN_REPEAT_S, now=1.0
    )
    assert (
        should_emit_ceo(
            "hold_pnl", fp, min_repeat_s=HOLD_PNL_MIN_REPEAT_S, now=1.0 + 3600
        )
        is False
    )
    assert should_emit_ceo(
        "hold_pnl",
        fp,
        min_repeat_s=HOLD_PNL_MIN_REPEAT_S,
        now=1.0 + HOLD_PNL_MIN_REPEAT_S,
    )


def test_fingerprint_includes_band_and_mode():
    d = _digest(equity="982", breakers=True)
    fp = digest_fingerprint(d, hold_kind="pnl")
    assert "paper" in fp
    assert "at" in fp
    assert "pnl" in fp


def test_hourly_skips_acciones_when_ceo_plain(paper_env, monkeypatch):
    from app.services import desk_status_tasks as mod

    reset_debounce_memory()
    monkeypatch.delenv("TELEGRAM_DESK_VERBOSE", raising=False)
    d = _digest(equity="982", breakers=True)
    d.full_telegram_payload = MagicMock(return_value=d.ceo_digest_text())
    rem = {
        "acted": False,
        "action": "hold_trading_reason",
        "breaker_reason": "Demasiadas pérdidas consecutivas: 5",
    }
    with (
        patch("app.core.desk_hourly_status.is_enabled", return_value=True),
        patch("app.core.desk_hourly_status.build_live_digest", return_value=d),
        patch(
            "app.core.desk_auto_remediation.maybe_remediate_stale_system_integrity",
            return_value=rem,
        ),
        patch.object(mod, "_telegram", return_value=True) as tg,
    ):
        out = mod.send_desk_hourly_digest()
    assert out["ok"] is True
    bodies = [str(c.args[0]) for c in tg.call_args_list]
    assert any("Freno de protección" in b or "Cómo va la prueba" in b for b in bodies)
    assert not any("DESK AUTO · ACCIONES" in b for b in bodies)
    assert not any("[HUMANO]" in b for b in bodies)

    tg.reset_mock()
    with (
        patch("app.core.desk_hourly_status.is_enabled", return_value=True),
        patch("app.core.desk_hourly_status.build_live_digest", return_value=d),
        patch(
            "app.core.desk_auto_remediation.maybe_remediate_stale_system_integrity",
            return_value=rem,
        ),
        patch.object(mod, "_telegram", return_value=True) as tg2,
    ):
        mod.send_desk_hourly_digest()
    assert tg2.call_count == 0


def _am_alert(**kwargs):
    labels = kwargs.pop("labels", None) or {
        "alertname": "PaperSnapshotStale20m",
        "instance": "flower:5555",
        "job": "flower",
    }
    return {
        "status": kwargs.get("status", "firing"),
        "labels": labels,
        "annotations": kwargs.get(
            "annotations",
            {"summary": "Snapshot portfolio >20m sin refresh"},
        ),
        "startsAt": kwargs.get("startsAt", "2026-08-12T17:09:06.254Z"),
        "endsAt": kwargs.get("endsAt", "0001-01-01T00:00:00Z"),
    }


def test_ceo_drops_flower_snapshot_stale_false_positive():
    reset_debounce_memory()
    text = format_alertmanager_ceo(
        {"alerts": [_am_alert()]},
        "warning",
    )
    assert text is None
    celery_only = format_alertmanager_ceo(
        {
            "alerts": [
                _am_alert(
                    labels={
                        "alertname": "PaperSnapshotStale20m",
                        "instance": "flower:5555",
                        "job": "gridbot-celery",
                    }
                )
            ]
        },
        "warning",
    )
    assert celery_only is None


def test_ceo_drops_resolved_snapshot_stale():
    reset_debounce_memory()
    text = format_alertmanager_ceo(
        {
            "alerts": [
                _am_alert(
                    status="resolved",
                    labels={
                        "alertname": "PaperSnapshotStale20m",
                        "instance": "gridbot-api:8000",
                        "job": "gridbot-api",
                    },
                    endsAt="2026-08-13T10:00:00Z",
                )
            ]
        },
        "warning",
    )
    assert text is None


def test_ceo_humanizes_api_snapshot_stale_without_flower_or_epoch():
    reset_debounce_memory()
    text = format_alertmanager_ceo(
        {
            "alerts": [
                _am_alert(
                    labels={
                        "alertname": "PaperSnapshotStale20m",
                        "instance": "gridbot-api:8000",
                        "job": "gridbot-api",
                    },
                    endsAt="0001-01-01T00:00:00Z",
                )
            ]
        },
        "warning",
    )
    assert text is not None
    assert "flower" not in text.lower()
    assert "0001-01-01" not in text
    assert "PaperSnapshotStale" not in text
    assert "Dinero real: NO" in text
    assert "20 minutos" in text or "chequeo" in text.lower()


def test_ceo_alertmanager_debounce_same_stale():
    reset_debounce_memory()
    payload = {
        "alerts": [
            _am_alert(
                labels={
                    "alertname": "PaperSnapshotStale20m",
                    "instance": "gridbot-api:8000",
                    "job": "gridbot-api",
                }
            )
        ]
    }
    first = format_alertmanager_ceo(payload, "warning")
    second = format_alertmanager_ceo(payload, "warning")
    assert first is not None
    assert second is None
