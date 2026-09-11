"""Capa A auto-tear alineada a Docs/TEAR_SHEET_PAPER_30D.md §1.

Paper-only. Decimal. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.core.desk_tear_capa_a import (
    collect_tear_snapshot,
    render_tear_markdown,
)


def _write_so_t(
    tmp_path: Path,
    *,
    fills: list | None = None,
    samples: list | None = None,
    extra_led: dict | None = None,
) -> None:
    led = {
        "initial_cash": "1000",
        "cash": "989.99",
        "deployed_capital": "200",
        "fees_total_usdt": "0.01000004",
        "slippage_total_usdt": "0.002",
        "realized_gross_pnl_usdt": "0.05",
        "realized_net_pnl_usdt": "-0.06",
        "fills": fills
        if fills is not None
        else [
            {
                "side": "BUY",
                "quantity": "0.0053",
                "commission_usdt": "0.01000004",
            }
        ],
        "cycles": [{"state": "open"}],
    }
    if extra_led:
        led.update(extra_led)
    series = {
        "config_hash": "630abf63e4ff9e3a",
        "samples": samples
        if samples is not None
        else [
            {
                "at": "2026-08-14T18:00:00+00:00",
                "equity": "999.94",
                "cash": "989.99",
                "inventory_value": "9.95",
                "config_hash": "630abf63e4ff9e3a",
                "daily_close_at": None,
            }
        ],
    }
    (tmp_path / "paper_equity_ledger.json").write_text(json.dumps(led), encoding="utf-8")
    (tmp_path / "paper_equity_series.json").write_text(
        json.dumps(series), encoding="utf-8"
    )


def _row(md: str, gate_id: str) -> str:
    for line in md.splitlines():
        if line.startswith(f"| **{gate_id}** |"):
            return line
    raise AssertionError(f"missing row {gate_id}")


def test_a1_fail_si_hash_unico_distinto_al_expected(
    tmp_path: Path, monkeypatch
) -> None:
    """Regresión RCA sticky: un solo hash ≠ expected → A1 FAIL (no PASS)."""
    sticky = "ac1cb59676abbaa42a9e1409809ee3b7009ae5114e15055615a7a1ff63b4b219"
    expected = "ff6a35fcf84bf91c1da9ea81116265a3789f1d85e5456d19622897c82ed7f5c4"
    monkeypatch.setenv("GRID_CONFIG_HASH", expected)
    series = {
        "config_hash": sticky,
        "samples": [
            {
                "at": "2026-08-27T00:00:00+00:00",
                "equity": "999.02",
                "cash": "999.02",
                "inventory_value": "0",
                "config_hash": sticky,
                "daily_close_at": None,
            }
        ],
    }
    _write_so_t(tmp_path, samples=series["samples"])
    # Header sticky explícito (unicidad sola no basta).
    (tmp_path / "paper_equity_series.json").write_text(
        json.dumps(series), encoding="utf-8"
    )
    snap = collect_tear_snapshot(
        telemetry_dir=tmp_path,
        when=datetime(2026, 8, 27, 0, 15, tzinfo=timezone.utc),
    )
    md = render_tear_markdown(snap)
    row = _row(md, "A1")
    assert "FAIL" in row
    assert "expected" in row.lower() or "≠" in row


def test_a1_pass_si_unico_igual_al_expected(tmp_path: Path, monkeypatch) -> None:
    expected = "ff6a35fcf84bf91c1da9ea81116265a3789f1d85e5456d19622897c82ed7f5c4"
    monkeypatch.setenv("GRID_CONFIG_HASH", expected)
    samples = [
        {
            "at": "2026-08-27T00:00:00+00:00",
            "equity": "999.02",
            "cash": "999.02",
            "inventory_value": "0",
            "config_hash": expected,
            "daily_close_at": None,
        }
    ]
    _write_so_t(tmp_path, samples=samples)
    (tmp_path / "paper_equity_series.json").write_text(
        json.dumps({"config_hash": expected, "samples": samples}),
        encoding="utf-8",
    )
    snap = collect_tear_snapshot(
        telemetry_dir=tmp_path,
        when=datetime(2026, 8, 27, 0, 15, tzinfo=timezone.utc),
    )
    assert "PASS" in _row(render_tear_markdown(snap), "A1")


def test_a1_fail_si_hay_dos_hashes(tmp_path: Path) -> None:
    _write_so_t(
        tmp_path,
        samples=[
            {
                "at": "2026-08-14T18:00:00+00:00",
                "equity": "999.94",
                "cash": "989.99",
                "inventory_value": "9.95",
                "config_hash": "aaaaaaaaaaaaaaaa",
            },
            {
                "at": "2026-08-14T18:10:00+00:00",
                "equity": "999.94",
                "cash": "989.99",
                "inventory_value": "9.95",
                "config_hash": "bbbbbbbbbbbbbbbb",
            },
        ],
    )
    snap = collect_tear_snapshot(
        telemetry_dir=tmp_path,
        when=datetime(2026, 8, 14, 18, 15, tzinfo=timezone.utc),
    )
    md = render_tear_markdown(snap)
    assert "FAIL" in _row(md, "A1")
    assert "PROMOTE_LIVE: NO" in md


def test_a3_reconcilia_equity_cash_inventario(tmp_path: Path) -> None:
    _write_so_t(tmp_path)
    snap = collect_tear_snapshot(
        telemetry_dir=tmp_path,
        when=datetime(2026, 8, 14, 18, 15, tzinfo=timezone.utc),
    )
    assert snap["recon_error_pct"] is not None
    assert Decimal(str(snap["recon_error_pct"])) <= Decimal("0.1")
    md = render_tear_markdown(snap)
    assert "PASS" in _row(md, "A3")
    assert "effective_mode=" not in _row(md, "A3")


def test_a5_exige_commission_en_fills(tmp_path: Path) -> None:
    _write_so_t(tmp_path, fills=[{"side": "BUY", "quantity": "0.0053"}])
    snap = collect_tear_snapshot(
        telemetry_dir=tmp_path,
        when=datetime(2026, 8, 14, 18, 15, tzinfo=timezone.utc),
    )
    md = render_tear_markdown(snap)
    assert "FAIL" in _row(md, "A5")


def test_a8_es_paper_sin_force_real_no_fills(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.delenv("FORCE_REAL_MODE", raising=False)
    _write_so_t(tmp_path)
    snap = collect_tear_snapshot(
        telemetry_dir=tmp_path,
        when=datetime(2026, 8, 14, 18, 15, tzinfo=timezone.utc),
    )
    md = render_tear_markdown(snap)
    assert "PASS" in _row(md, "A8")
    assert "fills=" not in _row(md, "A8")
