"""Contrato dashboards L0 — uid, datasource prometheus, job filters, legado eliminado.

Paper-only. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH_DIR = ROOT / "docker/grafana/dashboards"

KEEP = {
    "gridbot-health-sre.json": "gridbot-health-sre",
    "gridbot-ceo-auto.json": "gridbot-ceo-auto",
    "gridbot-paper-l0.json": "gridbot-paper-l0",
    "trading-profitability-dashboard.json": "trading-profitability",
    "gridbot-pg-sre.json": "gridbot-pg-sre",
    "gridbot-pipeline-ingestion.json": "gridbot-pipeline-ingestion",
    "gridbot-celery.json": "gridbot-celery",
}

REMOVED = {
    "gridbot-overview.json",
    "gridbot-simple-dashboard.json",
    "gridbot-trading-dashboard.json",
    "postgresql-overview.json",
}

FAKE_DS = "PBFA97CFB590B2093"


def _load(name: str) -> dict:
    return json.loads((DASH_DIR / name).read_text(encoding="utf-8"))


def test_legacy_dashboards_removed():
    for name in REMOVED:
        assert not (DASH_DIR / name).exists(), f"legacy dashboard still present: {name}"


def test_l0_dashboard_inventory():
    on_disk = {p.name for p in DASH_DIR.glob("*.json")}
    assert on_disk == set(KEEP.keys())


def test_no_fake_prometheus_datasource_uid():
    for name in KEEP:
        raw = (DASH_DIR / name).read_text(encoding="utf-8")
        assert FAKE_DS not in raw, name


def test_health_sre_job_filters_and_merged_overview():
    data = _load("gridbot-health-sre.json")
    raw = (DASH_DIR / "gridbot-health-sre.json").read_text(encoding="utf-8")
    assert data["uid"] == "gridbot-health-sre"
    assert 'job=\\"gridbot-api\\"' in raw or 'job="gridbot-api"' in raw
    assert "integrity_score" in raw
    assert "invalid_symbol_total" in raw
    assert "cash_balance_usdt" in raw
    titles = [p.get("title") for p in data["panels"]]
    assert "Integridad & portfolio ops (ex-Overview)" in titles


def test_ceo_auto_job_filters_on_mode_and_orders():
    raw = (DASH_DIR / "gridbot-ceo-auto.json").read_text(encoding="utf-8")
    assert "trading_effective_mode{job=" in raw.replace("\\", "")
    assert "gridbot_orders_total{job=" in raw.replace("\\", "")
    assert "binance_ip_rejected{job=" in raw.replace("\\", "")
    assert FAKE_DS not in raw


def test_paper_l0_all_panels_filter_gridbot_api():
    data = _load("gridbot-paper-l0.json")
    raw = (DASH_DIR / "gridbot-paper-l0.json").read_text(encoding="utf-8")
    assert data["uid"] == "gridbot-paper-l0"
    assert 'job=\\"gridbot-api\\"' in raw or 'job="gridbot-api"' in raw
    assert "breaker_state" in raw


def test_profitability_defer_tags_and_job_filter():
    data = _load("trading-profitability-dashboard.json")
    assert data["uid"] == "trading-profitability"
    assert "defer" in data["tags"]
    assert "paper" in data["tags"]
    raw = (DASH_DIR / "trading-profitability-dashboard.json").read_text(encoding="utf-8")
    assert 'job=\\"gridbot-api\\"' in raw or 'job="gridbot-api"' in raw
    assert "gridbot-ceo-auto" in raw


def test_health_sre_integrity_and_invalid_symbol_avoid_no_data():
    data = _load("gridbot-health-sre.json")
    integ = next(p for p in data["panels"] if p.get("id") == 14)
    for t in integ["targets"]:
        assert "or on() vector(0)" in t["expr"]
    inv = next(p for p in data["panels"] if p.get("id") == 15)
    assert "or on()" in inv["targets"][0]["expr"]
    assert "_none_" in inv["targets"][0]["expr"] or "vector(0)" in inv[
        "targets"
    ][0]["expr"]


def test_profitability_total_ops_not_red_on_volume():
    data = _load("trading-profitability-dashboard.json")
    ops = next(
        p for p in data["panels"] if "Total de Operaciones" in p.get("title", "")
    )
    steps = ops["fieldConfig"]["defaults"]["thresholds"]["steps"]
    assert not any(s.get("color") == "red" for s in steps)
    colors = {s.get("color") for s in steps}
    assert colors <= {"blue", "green", "text"}
    brk = next(p for p in data["panels"] if "Breakers" in p.get("title", ""))
    bsteps = brk["fieldConfig"]["defaults"]["thresholds"]["steps"]
    assert any(s.get("value") == 1 and s.get("color") == "red" for s in bsteps)