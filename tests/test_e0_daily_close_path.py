"""WS-2 B5 — path E_0: daily_close_at anclado sin inventar mid."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.paper_equity_ledger import (
    PaperEquitySeries,
    daily_close_anchor,
    reset_paper_telemetry,
)
from scripts.capture_paper_e0_daily_close import capture, window_status
from scripts.quarantine_legacy_paper_positions import quarantine

D = Decimal
UTC = timezone.utc


@pytest.fixture(autouse=True)
def _clean():
    reset_paper_telemetry()
    yield
    reset_paper_telemetry()


def test_daily_close_anchor_sets_daily_close_at_on_record(tmp_path: Path):
    """Evidencia JSON: sample en ±30m 00:00 UTC → daily_close_at no null."""
    series_path = tmp_path / "paper_equity_series.json"
    series = PaperEquitySeries(
        config_hash="630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f",
        deployed_capital=D("200"),
        storage_path=series_path,
    )
    at = datetime(2026, 8, 6, 0, 12, tzinfo=UTC)
    sample = series.record(
        D("1000"),
        at=at,
        cash=D("1000"),
        inventory_value=D("0"),
        deployed_capital=D("200"),
        config_hash="630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f",
    )

    assert daily_close_anchor(at) is not None
    assert sample["daily_close_at"] == "2026-08-06T00:00:00+00:00"
    assert sample["config_hash"].startswith("630abf63")

    on_disk = json.loads(series_path.read_text())
    assert on_disk["samples"][-1]["daily_close_at"] is not None
    assert on_disk["samples"][-1]["daily_close_at"] == sample["daily_close_at"]


def test_window_status_outside_reports_next_open():
    noon = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    status = window_status(noon)
    assert status["in_window"] is False
    assert status["anchor"] is None
    assert "2026-08-05T23:30:00" in status["next_window_opens_at"]


def test_window_status_inside_near_midnight():
    near = datetime(2026, 8, 6, 0, 10, tzinfo=UTC)
    status = window_status(near)
    assert status["in_window"] is True
    assert status["anchor"] == "2026-08-06T00:00:00+00:00"


def test_capture_outside_window_does_not_write(monkeypatch):
    monkeypatch.setattr(
        "app.core.trading_mode.get_trading_mode_snapshot",
        lambda: {
            "effective_mode": "paper",
            "paper_trading": True,
            "force_real_mode": False,
        },
    )
    monkeypatch.setattr(
        "app.core.paper_equity_ledger.resolve_grid_config_hash",
        lambda: "630abf63e4ff9e3a8499d68afe8c9ff09b2752709df667b3dc0ceea840744f6f",
    )
    noon = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    out = capture(write=True, now=noon)
    assert out["ok"] is False
    assert out["window"]["in_window"] is False
    assert "fuera de ventana" in out["reason"]


def test_quarantine_moves_positions_without_touching_telemetry(tmp_path: Path):
    state = tmp_path / "paper_trading_state.json"
    state.write_text(
        json.dumps(
            {
                "positions": {
                    "BNBUSDT": {"quantity": 0.1, "avg_price": 850.0}
                },
                "trades": [],
            }
        )
    )
    telemetry = tmp_path / "paper_telemetry"
    telemetry.mkdir()
    series = telemetry / "paper_equity_series.json"
    series.write_text('{"samples":[{"equity":"1000","daily_close_at":null}]}')

    out = quarantine(state, write=True)
    assert out["action"] == "quarantined"
    data = json.loads(state.read_text())
    assert data["positions"] == {}
    assert "BNBUSDT" in data["_quarantined_positions"]["positions"]
    assert data["legacy_positions_reconciled"] is True
    # Serie intacta
    assert "1000" in series.read_text()
