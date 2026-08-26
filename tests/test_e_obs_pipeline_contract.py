"""Contrato E-OBS-PIPELINE — dash ingesta + sidecar + scrape API.

Paper-only. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "docker/grafana/dashboards/gridbot-pipeline-ingestion.json"
PROM = ROOT / "docker/prometheus/prometheus.yml"
METRICS = ROOT / "app/core/metrics.py"


def test_pipeline_dashboard_uid_and_job_filter():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    assert data["uid"] == "gridbot-pipeline-ingestion"
    raw = DASH.read_text(encoding="utf-8")
    assert 'job=\\"gridbot-api\\"' in raw or 'job="gridbot-api"' in raw
    assert "http_requests_total" in raw
    assert "gridbot_items_processed_total" in raw


def test_pipeline_dashboard_uses_http_not_legacy_pipeline_api():
    raw = DASH.read_text(encoding="utf-8")
    assert "pipeline_api_requests_total" not in raw
    assert "http_request_duration_seconds_bucket" in raw


def test_prometheus_scrapes_gridbot_api():
    text = PROM.read_text(encoding="utf-8")
    assert "job_name: 'gridbot-api'" in text
    assert "api:8000" in text
    assert "/metrics" in text


def test_gridbot_pipeline_counters_defined():
    text = METRICS.read_text(encoding="utf-8")
    assert "gridbot_items_processed_total" in text
    assert "gridbot_items_dropped_total" in text
    assert "gridbot_pipeline_errors_total" in text


def test_pipeline_sidecar_hydrate_on_metrics():
    prom = (ROOT / "app/api/prometheus.py").read_text(encoding="utf-8")
    assert "hydrate_pipeline_counters" in prom
    assert "publish_obs_gauges" in prom


def test_pipeline_dashboard_errors_by_type_handles_empty():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    panel = next(p for p in data["panels"] if p.get("id") == 5)
    expr = panel["targets"][0]["expr"]
    assert "gridbot_pipeline_errors_total" in expr
    assert "or on()" in expr
    assert "vector(0)" in expr


def test_pipeline_sidecar_bump_and_hydrate_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    from app.core.pipeline_metrics_sidecar import (
        _APPLIED,
        bump_labeled_counter,
        hydrate_pipeline_counters,
    )

    _APPLIED.clear()
    bump_labeled_counter("gridbot_items_processed_total", stage="test")
    bump_labeled_counter(
        "db_writes_total",
        table="portfolio_snapshots",
        operation="insert",
        status="ok",
    )
    hydrate_pipeline_counters()
    from prometheus_client import generate_latest

    body = generate_latest().decode()
    assert "gridbot_items_processed_total" in body
    assert "db_writes_total" in body
