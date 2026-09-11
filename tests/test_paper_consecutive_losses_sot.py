"""En paper, pérdidas consecutivas se miden en el ledger de esta ventana, no en Trade DB.

Sin esto un T0 limpio hereda el HOLD de 5 pérdidas de la corrida burn-in.
Paper-only. Decimal. PROMOTE_LIVE: NO.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.auto_circuit_breaker import (
    AutoCircuitBreaker,
    consecutive_loss_trip_threshold,
    consecutive_losses_from_closed_cycles,
    paper_trial_started_at,
    paper_window_loss_metrics,
)


def _cycle(*, net: str, closed: bool = True, at: str = "2026-08-13T12:00:00+00:00"):
    return SimpleNamespace(
        state="closed" if closed else "open",
        closed_at=datetime.fromisoformat(at) if closed else None,
        net_pnl_usdt=Decimal(net),
    )


def test_ledger_vacio_cero_racha():
    assert consecutive_losses_from_closed_cycles([]) == 0


def test_racha_desde_el_cierre_mas_reciente():
    cycles = [
        _cycle(net="0.01", at="2026-08-10T10:00:00+00:00"),
        _cycle(net="-0.02", at="2026-08-11T10:00:00+00:00"),
        _cycle(net="-0.03", at="2026-08-12T10:00:00+00:00"),
    ]
    assert consecutive_losses_from_closed_cycles(cycles) == 2


def test_una_ganancia_corta_la_racha():
    cycles = [
        _cycle(net="-0.01", at="2026-08-10T10:00:00+00:00"),
        _cycle(net="0.02", at="2026-08-11T10:00:00+00:00"),
        _cycle(net="-0.03", at="2026-08-12T10:00:00+00:00"),
    ]
    assert consecutive_losses_from_closed_cycles(cycles) == 1


def test_ignora_ciclos_abiertos():
    cycles = [
        _cycle(net="-0.50", closed=False),
        _cycle(net="-0.01", at="2026-08-13T10:00:00+00:00"),
    ]
    assert consecutive_losses_from_closed_cycles(cycles) == 1


def test_watermark_since_ignora_closes_anteriores_o_iguales_a_t0():
    """Prueba SI: racha SoT 19 no cuenta; solo closed_at > t0."""
    t0 = datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    cycles = [
        _cycle(net="-0.01", at="2026-08-20T10:00:00+00:00"),
        _cycle(net="-0.01", at="2026-08-26T15:45:37+00:00"),  # watermark = t0
        _cycle(net="-0.02", at="2026-08-29T12:00:00+00:00"),
        _cycle(net="-0.03", at="2026-08-29T18:00:00+00:00"),
    ]
    assert consecutive_losses_from_closed_cycles(cycles) == 4
    assert consecutive_losses_from_closed_cycles(cycles, since=t0) == 2


def test_watermark_t0_sin_microsegundos_no_cuenta_el_close_del_mismo_segundo():
    t0 = datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    cycles = [
        _cycle(net="-0.01", at="2026-08-26T15:45:37.370240+00:00"),
        _cycle(net="-0.02", at="2026-08-29T12:00:00+00:00"),
    ]
    assert consecutive_losses_from_closed_cycles(cycles, since=t0) == 1


def test_watermark_since_una_ganancia_post_t0_corta_solo_la_ventana():
    t0 = datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    cycles = [
        _cycle(net="-0.01", at="2026-08-26T15:45:37+00:00"),
        _cycle(net="0.05", at="2026-08-29T12:00:00+00:00"),
        _cycle(net="-0.02", at="2026-08-29T18:00:00+00:00"),
    ]
    assert consecutive_losses_from_closed_cycles(cycles, since=t0) == 1


def test_trial_env_threshold_2_solo_si_hay_t0(monkeypatch):
    monkeypatch.delenv("PAPER_TRIAL_STARTED_AT", raising=False)
    monkeypatch.setenv("PAPER_TRIAL_STREAK_THRESHOLD", "2")
    assert paper_trial_started_at() is None
    assert consecutive_loss_trip_threshold() == 5

    monkeypatch.setenv("PAPER_TRIAL_STARTED_AT", "2026-08-26T15:45:37+00:00")
    started = paper_trial_started_at()
    assert started == datetime(2026, 8, 26, 15, 45, 37, tzinfo=timezone.utc)
    assert consecutive_loss_trip_threshold() == 2


def test_early_warn_env_no_cambia_el_trip(monkeypatch):
    """PAPER_EARLY_STREAK_WARN=2 no sustituye el umbral duro."""
    monkeypatch.setenv("PAPER_EARLY_STREAK_WARN", "2")
    monkeypatch.delenv("PAPER_TRIAL_STARTED_AT", raising=False)
    assert consecutive_loss_trip_threshold() == 5


def test_ventana_vacia_metricas_cero():
    metrics = paper_window_loss_metrics(
        [],
        now=datetime(2026, 8, 13, 23, 0, tzinfo=timezone.utc),
        initial_cash=Decimal("1000"),
    )
    assert metrics["total_loss_pct"] == 0.0
    assert metrics["daily_loss_pct"] == 0.0
    assert metrics["hourly_loss_pct"] == 0.0
    assert metrics["total_loss_usd"] == 0.0
    assert metrics["last_closed_at"] is None


def test_ventana_daily_cero_expone_last_closed_at():
    now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    cycles = [
        _cycle(net="-1", at="2026-08-26T18:00:00+00:00"),
    ]
    metrics = paper_window_loss_metrics(
        cycles, now=now, initial_cash=Decimal("1000")
    )
    assert metrics["daily_loss_pct"] == 0.0
    assert "2026-08-26" in (metrics["last_closed_at"] or "")


def test_format_daily_metrics_log_sin_closes_hoy():
    from app.core.auto_circuit_breaker import format_daily_metrics_log

    msg = format_daily_metrics_log(
        {
            "total_loss_pct": 0.001,
            "daily_loss_pct": 0.0,
            "last_closed_at": "2026-08-26T18:00:00+00:00",
        }
    )
    assert "sin closes hoy" in msg
    assert "2026-08-26" in msg
    assert "Total=" in msg


def test_metricas_solo_cierres_negativos_de_esta_ventana():
    now = datetime(2026, 8, 13, 23, 0, tzinfo=timezone.utc)
    cycles = [
        _cycle(net="-10", at=(now - timedelta(days=3)).isoformat()),
        _cycle(net="-5", at=(now - timedelta(hours=2)).isoformat()),
        _cycle(net="2", at=(now - timedelta(minutes=10)).isoformat()),
        _cycle(net="-1", at=(now - timedelta(minutes=10)).isoformat()),
    ]
    metrics = paper_window_loss_metrics(
        cycles, now=now, initial_cash=Decimal("1000")
    )
    assert metrics["total_loss_usd"] == 16.0
    assert metrics["total_loss_pct"] == 0.016
    assert metrics["daily_loss_usd"] == 6.0
    assert metrics["hourly_loss_usd"] == 1.0


async def test_paper_sot_ledger_vacio_no_hereda_trades_db():
    auto = AutoCircuitBreaker(breakers=MagicMock())
    auto.breakers.activate_breaker = AsyncMock()
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        SimpleNamespace(profit_loss=-1.0) for _ in range(6)
    ]
    ledger = MagicMock()
    ledger.closed_cycles.return_value = []
    results = {"breakers_activated": [], "reasons": []}
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_equity_ledger.reload_paper_ledger_from_disk",
        return_value=ledger,
    ):
        await auto._check_consecutive_losses(db, results)
    assert results["breakers_activated"] == []
    auto.breakers.activate_breaker.assert_not_called()
    db.query.assert_not_called()


async def test_paper_sot_cinco_cierres_rojos_activa_si():
    auto = AutoCircuitBreaker(breakers=MagicMock())
    auto.breakers.activate_breaker = AsyncMock()
    ledger = MagicMock()
    ledger.closed_cycles.return_value = [
        _cycle(net="-0.01", at=f"2026-08-1{i}T10:00:00+00:00") for i in range(3, 8)
    ]
    results = {"breakers_activated": [], "reasons": []}
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_equity_ledger.reload_paper_ledger_from_disk",
        return_value=ledger,
    ):
        await auto._check_consecutive_losses(MagicMock(), results)
    assert "system_integrity" in results["breakers_activated"]
    auto.breakers.activate_breaker.assert_awaited()


async def test_paper_trial_ignora_racha_historica_y_no_tripa_con_una_perdida(
    monkeypatch,
):
    monkeypatch.setenv("PAPER_TRIAL_STARTED_AT", "2026-08-26T15:45:37+00:00")
    monkeypatch.setenv("PAPER_TRIAL_STREAK_THRESHOLD", "2")
    monkeypatch.setenv("PAPER_EARLY_STREAK_WARN", "2")
    auto = AutoCircuitBreaker(breakers=MagicMock())
    auto.breakers.activate_breaker = AsyncMock()
    ledger = MagicMock()
    ledger.closed_cycles.return_value = [
        _cycle(net="-0.01", at="2026-08-20T10:00:00+00:00"),
        _cycle(net="-0.01", at="2026-08-26T15:45:37+00:00"),
        _cycle(net="-0.02", at="2026-08-29T12:00:00+00:00"),
    ]
    results = {"breakers_activated": [], "reasons": []}
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_equity_ledger.reload_paper_ledger_from_disk",
        return_value=ledger,
    ), patch(
        "app.core.breaker_override.check_and_consume_override",
        return_value=MagicMock(
            skip_activation=False, override=None, force_reduce_only=False
        ),
    ):
        await auto._check_consecutive_losses(MagicMock(), results)
    assert results["breakers_activated"] == []
    auto.breakers.activate_breaker.assert_not_called()


async def test_paper_trial_dos_perdidas_post_t0_activa_si(monkeypatch):
    monkeypatch.setenv("PAPER_TRIAL_STARTED_AT", "2026-08-26T15:45:37+00:00")
    monkeypatch.setenv("PAPER_TRIAL_STREAK_THRESHOLD", "2")
    auto = AutoCircuitBreaker(breakers=MagicMock())
    auto.breakers.activate_breaker = AsyncMock()
    ledger = MagicMock()
    ledger.closed_cycles.return_value = [
        _cycle(net="-0.01", at="2026-08-26T15:45:37+00:00"),
        _cycle(net="-0.02", at="2026-08-29T12:00:00+00:00"),
        _cycle(net="-0.03", at="2026-08-29T18:00:00+00:00"),
    ]
    results = {"breakers_activated": [], "reasons": []}
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_equity_ledger.reload_paper_ledger_from_disk",
        return_value=ledger,
    ), patch(
        "app.core.breaker_override.check_and_consume_override",
        return_value=MagicMock(
            skip_activation=False, override=None, force_reduce_only=False
        ),
    ):
        await auto._check_consecutive_losses(MagicMock(), results)
    assert "system_integrity" in results["breakers_activated"]
    auto.breakers.activate_breaker.assert_awaited()


async def test_paper_trial_override_expirado_sin_close_fuerza_reduce_only(
    monkeypatch,
):
    monkeypatch.setenv("PAPER_TRIAL_STARTED_AT", "2026-08-26T15:45:37+00:00")
    monkeypatch.setenv("PAPER_TRIAL_STREAK_THRESHOLD", "2")
    auto = AutoCircuitBreaker(breakers=MagicMock())
    auto.breakers.activate_breaker = AsyncMock()
    ledger = MagicMock()
    ledger.closed_cycles.return_value = [
        _cycle(net="-0.01", at="2026-08-26T15:45:37+00:00"),
    ]
    results = {"breakers_activated": [], "reasons": []}
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_equity_ledger.reload_paper_ledger_from_disk",
        return_value=ledger,
    ), patch(
        "app.core.breaker_override.check_and_consume_override",
        return_value=MagicMock(
            skip_activation=False, override=None, force_reduce_only=True
        ),
    ):
        await auto._check_consecutive_losses(MagicMock(), results)
    assert "system_integrity" in results["breakers_activated"]
    reason = results["reasons"][0]
    assert "override" in reason.lower()
    auto.breakers.activate_breaker.assert_awaited()


def test_reload_paper_ledger_from_disk_descarta_singleton(tmp_path, monkeypatch):
    from app.core import paper_equity_ledger as pel

    path = tmp_path / "paper_equity_ledger.json"
    first = pel.PaperEquityLedger(
        initial_cash=Decimal("1000"),
        deployed_capital=Decimal("200"),
        storage_path=path,
    )
    first.save()
    monkeypatch.setattr(pel, "_telemetry_dir", lambda: tmp_path)
    pel._ledger = first
    reloaded = pel.reload_paper_ledger_from_disk()
    assert reloaded is not first
    assert float(reloaded.cash) == 1000.0
    pel._ledger = None
