"""B4 — Facade CEO `pnl_mtd` desde PaperEquitySeries (MtM).

Contrato: `app.core.pnl_ledger.get_pnl_summary()` alimenta el adaptador de
`ceo_overview` (ADR-005). Sin serie MtM → unavailable honesto (nunca ceros
inventados). Con fixtures → delta Decimal MTD.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core import ceo_overview
from app.core.paper_equity_ledger import PaperEquitySeries, reset_paper_telemetry
from app.core.pnl_ledger import (
    PnlUnavailableError,
    compute_pnl_from_series,
    get_pnl_summary,
)

D = Decimal
UTC = timezone.utc


@pytest.fixture(autouse=True)
def _clean_paper_singletons():
    reset_paper_telemetry()
    yield
    reset_paper_telemetry()


def _at(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


# ─────────────────────────────────────────────────────────────────────────────
# Sin datos → unavailable (no inventar P&L)
# ─────────────────────────────────────────────────────────────────────────────


def test_compute_sin_samples_raises_unavailable():
    series = PaperEquitySeries()

    with pytest.raises(PnlUnavailableError, match="sin serie equity MtM"):
        compute_pnl_from_series(series, now=_at(2026, 8, 5))


def test_get_pnl_summary_sin_datos_raises(monkeypatch):
    empty = PaperEquitySeries()
    monkeypatch.setattr(
        "app.core.pnl_ledger.get_paper_equity_series", lambda: empty
    )

    with pytest.raises(PnlUnavailableError):
        get_pnl_summary(now=_at(2026, 8, 5))


def test_ceo_overview_pnl_mtd_unavailable_sin_serie(monkeypatch):
    """El overview degrada a unavailable con razón; value es None (no cero)."""
    empty = PaperEquitySeries()
    monkeypatch.setattr(
        "app.core.pnl_ledger.get_paper_equity_series", lambda: empty
    )
    monkeypatch.setattr(
        ceo_overview,
        "_import_optional",
        lambda name: (
            __import__("app.core.pnl_ledger", fromlist=["*"])
            if name == "app.core.pnl_ledger"
            else None
        ),
    )

    overview = ceo_overview.build_ceo_overview(now=_at(2026, 8, 5))
    widget = overview["pnl_mtd"]

    assert widget["status"] == "unavailable"
    assert widget["value"] is None
    assert widget["reason"]
    assert "cero" not in (widget["reason"] or "").lower()
    assert "MtM" in widget["reason"] or "serie" in widget["reason"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Con fixtures → delta MTD Decimal correcto
# ─────────────────────────────────────────────────────────────────────────────


def test_compute_mtd_delta_from_equity_series():
    """pnl_mtd = E_last − E_ancla_mes (Decimal exacto)."""
    series = PaperEquitySeries(deployed_capital=D("200"))
    series.record(D("1000.00"), at=_at(2026, 7, 31, 23))
    series.record(D("1005.00"), at=_at(2026, 8, 1, 12))
    series.record(D("1018.30"), at=_at(2026, 8, 5, 12))

    result = compute_pnl_from_series(series, now=_at(2026, 8, 5, 15))

    assert result["pnl_mtd"] == D("18.30")
    assert isinstance(result["pnl_mtd"], Decimal)
    assert result["equity_start"] == D("1000.00")
    assert result["equity_as_of"] == D("1018.30")
    assert result["basis"] == "mtm_equity_series"


def test_compute_mtd_without_pre_month_uses_first_daily_close_e0():
    """Sin sample pre-mes, el ancla MTD es el primer E_0 (cierre 00:00 UTC)."""
    series = PaperEquitySeries()
    series.record(D("560.00"), at=datetime(2026, 8, 2, 0, 5, tzinfo=UTC))
    series.record(D("575.50"), at=_at(2026, 8, 10))

    result = compute_pnl_from_series(series, now=_at(2026, 8, 10, 18))

    assert result["pnl_mtd"] == D("15.50")
    assert result["equity_start"] == D("560.00")
    assert result["anchor"] == "first_daily_close_in_month"


def test_intraday_ticks_without_e0_are_unavailable_never_zero():
    """CEO-5/N9: ticks flat sin daily_close_at no inventan pnl_mtd=0."""
    series = PaperEquitySeries()
    series.record(D("1000"), at=_at(2026, 8, 5, 20))
    series.record(D("1000"), at=_at(2026, 8, 5, 21))

    with pytest.raises(PnlUnavailableError, match="ancla usable|E_0|cierre diario"):
        compute_pnl_from_series(series, now=_at(2026, 8, 5, 21))


def test_compute_single_sample_is_unavailable():
    series = PaperEquitySeries()
    series.record(D("1000"), at=_at(2026, 8, 5))

    with pytest.raises(PnlUnavailableError, match="ancla usable|insuficiente|E_0"):
        compute_pnl_from_series(series, now=_at(2026, 8, 5, 18))


def test_ceo_overview_never_ok_zero_without_usable_series(monkeypatch):
    """Runtime bug: serie cash-only flat → unavailable+null, nunca ok/stale+0."""
    series = PaperEquitySeries()
    series.record(D("1000"), at=_at(2026, 8, 5, 20))
    series.record(D("1000"), at=_at(2026, 8, 5, 21))
    monkeypatch.setattr(
        "app.core.pnl_ledger.get_paper_equity_series", lambda: series
    )
    monkeypatch.setattr(
        ceo_overview,
        "_import_optional",
        lambda name: (
            __import__("app.core.pnl_ledger", fromlist=["*"])
            if name == "app.core.pnl_ledger"
            else None
        ),
    )

    overview = ceo_overview.build_ceo_overview(now=_at(2026, 8, 5, 21))
    widget = overview["pnl_mtd"]

    assert widget["status"] == "unavailable"
    assert widget["value"] is None
    assert widget["status"] != "ok" or widget["value"] not in (0, "0", Decimal("0"))


def test_get_pnl_summary_serializes_money_as_decimal_compatible(monkeypatch):
    series = PaperEquitySeries()
    series.record(D("200.00"), at=_at(2026, 7, 31))
    series.record(D("210.00"), at=_at(2026, 8, 3))
    monkeypatch.setattr(
        "app.core.pnl_ledger.get_paper_equity_series", lambda: series
    )

    payload = get_pnl_summary(now=_at(2026, 8, 3, 20))

    assert payload["pnl_mtd"] == D("10.00")
    assert payload["as_of"]
    assert "daily_pnl_pct" in payload


def test_daily_pnl_pct_from_last_two_daily_closes():
    series = PaperEquitySeries()
    series.record(D("1000"), at=datetime(2026, 8, 3, 0, 0, tzinfo=UTC))
    series.record(D("1010"), at=datetime(2026, 8, 4, 0, 0, tzinfo=UTC))
    series.record(D("1015"), at=datetime(2026, 8, 5, 0, 0, tzinfo=UTC))

    result = compute_pnl_from_series(series, now=_at(2026, 8, 5, 12))

    expected = (D("1015") / D("1010")) - 1
    assert result["daily_pnl_pct"] == expected
    assert result["pnl_mtd"] == D("15")


def test_ceo_overview_pnl_mtd_ok_with_series(monkeypatch):
    series = PaperEquitySeries()
    series.record(D("1000.00"), at=_at(2026, 7, 31))
    series.record(D("1018.30"), at=_at(2026, 8, 5))
    monkeypatch.setattr(
        "app.core.pnl_ledger.get_paper_equity_series", lambda: series
    )
    monkeypatch.setattr(
        ceo_overview,
        "_import_optional",
        lambda name: (
            __import__("app.core.pnl_ledger", fromlist=["*"])
            if name == "app.core.pnl_ledger"
            else None
        ),
    )

    overview = ceo_overview.build_ceo_overview(now=_at(2026, 8, 5, 16))
    widget = overview["pnl_mtd"]

    assert widget["status"] in {"ok", "stale"}
    assert Decimal(widget["value"]) == D("18.30")
    assert widget["unit"] == "usd"


def test_real_flat_mtd_with_pre_month_anchor_may_be_zero():
    """Cero legítimo: E_mes == E_ancla pre-mes con serie usable."""
    series = PaperEquitySeries()
    series.record(D("1000"), at=_at(2026, 7, 31, 23))
    series.record(D("1000"), at=_at(2026, 8, 5, 12))

    result = compute_pnl_from_series(series, now=_at(2026, 8, 5, 15))

    assert result["pnl_mtd"] == D("0")
    assert result["anchor"] == "pre_month_or_eom"
