"""TDD — tear Capa A auto + desk area actions (AS-1 / AS-2)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.core.desk_area_actions import (
    format_actions_telegram,
    plan_actions_for_areas,
)
from app.core.desk_tear_capa_a import (
    collect_tear_snapshot,
    render_tear_markdown,
    write_tear_capa_a,
)


def test_write_tear_capa_a_from_fixture(tmp_path: Path):
    tel = tmp_path / "tel"
    tel.mkdir()
    ops = tmp_path / "ops"
    ops.mkdir()
    led = {
        "initial_cash": "1000",
        "cash": "100",
        "deployed_capital": "200",
        "fees_total_usdt": "1.0",
        "slippage_total_usdt": "0.2",
        "realized_gross_pnl_usdt": "0.1",
        "realized_net_pnl_usdt": "0.01",
        "updated_at": "2026-08-09T12:00:00+00:00",
        "fills": [
            {"side": "BUY"},
            {"side": "BUY"},
            {"side": "SELL"},
        ],
        "cycles": [
            {"state": "open"},
            {"state": "closed"},
        ],
    }
    series = {
        "config_hash": "abc123deadbeef",
        "samples": [
            {
                "at": "2026-08-09T10:00:00+00:00",
                "equity": "1000",
                "config_hash": "abc123deadbeef",
                "daily_close_at": None,
            },
            {
                "at": "2026-08-09T11:00:00+00:00",
                "equity": "1000.5",
                "config_hash": "abc123deadbeef",
                "daily_close_at": "2026-08-09T00:00:00+00:00",
            },
        ],
    }
    (tel / "paper_equity_ledger.json").write_text(json.dumps(led), encoding="utf-8")
    (tel / "paper_equity_series.json").write_text(json.dumps(series), encoding="utf-8")

    path = write_tear_capa_a(
        telemetry_dir=tel,
        ops_dir=ops,
        when=datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc),
    )
    text = path.read_text(encoding="utf-8")
    assert "PROMOTE_LIVE: NO" in text
    assert "BUY 2" in text and "SELL 1" in text
    assert "N/A" in text
    assert path.name == "tear-capa-a-2026-08-09.md"


def test_plan_actions_risk_auto_after_remediate():
    areas = [
        SimpleNamespace(code="RISK", status="AT_RISK", deviation="breakers abiertos"),
        SimpleNamespace(code="MM", status="ON_TRACK", deviation=""),
    ]
    acts = plan_actions_for_areas(areas, remediation={"acted": True, "action": "reset"})
    assert len(acts) == 1
    assert acts[0].code == "RISK" and acts[0].auto is True
    msg = format_actions_telegram(acts)
    assert msg and "DESK AUTO" in msg and "PROMOTE_LIVE: NO" in msg


def test_collect_snap_empty(tmp_path: Path):
    snap = collect_tear_snapshot(
        telemetry_dir=tmp_path,
        when=datetime(2026, 8, 9, tzinfo=timezone.utc),
    )
    assert snap["n_fills"] == 0
    md = render_tear_markdown(snap)
    assert "PROMOTE_LIVE: NO" in md
