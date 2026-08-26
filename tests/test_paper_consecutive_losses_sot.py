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
    consecutive_losses_from_closed_cycles,
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
