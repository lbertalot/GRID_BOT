"""Contrato E-OBS-CELERY — dash Flower + redis queues + rules.

Paper-only. Sin red a Binance. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "docker/grafana/dashboards/gridbot-celery.json"
RULES = ROOT / "docker/prometheus/rules/gridbot_celery_sre.yml"
ALERTS = ROOT / "docker/prometheus/rules/alerts.yml"
COMPOSE_LOCAL = ROOT / "docker-compose.local.yml"
AM = ROOT / "docker/alertmanager/alertmanager.yml"
CELERY_APP = ROOT / "app/core/celery_app.py"


def test_celery_dashboard_uses_prometheus_uid_not_legacy():
    raw = DASH.read_text(encoding="utf-8")
    assert "PBFA97CFB590B2093" not in raw
    data = json.loads(raw)
    assert data["uid"] == "gridbot-celery"
    assert data["refresh"] == "30s"
    assert '"uid": "prometheus"' in raw or '"uid":"prometheus"' in raw


def test_celery_dashboard_filters_job_gridbot_celery():
    raw = DASH.read_text(encoding="utf-8")
    assert 'job=\\"gridbot-celery\\"' in raw or 'job="gridbot-celery"' in raw
    assert "flower_worker_online" in raw
    assert "flower_events_total" in raw
    assert "flower_task_runtime_seconds_bucket" in raw


def test_celery_dashboard_workers_red_at_zero_and_failure_rate_red_over_5():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    workers = next(p for p in data["panels"] if p.get("id") == 1)
    steps = workers["fieldConfig"]["defaults"]["thresholds"]["steps"]
    assert steps[0]["color"] == "red"
    assert steps[1]["value"] == 1
    failure = next(p for p in data["panels"] if p.get("id") == 5)
    fsteps = failure["fieldConfig"]["defaults"]["thresholds"]["steps"]
    assert any(s.get("value") == 5 and s.get("color") == "red" for s in fsteps)


def test_celery_dashboard_queue_uses_redis_exporter_keys():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    queue = next(p for p in data["panels"] if p.get("id") == 13)
    expr = queue["targets"][0]["expr"]
    assert "job=\"redis\"" in expr
    assert "celery|low" in expr


def test_compose_local_worker_events_and_redis_check_keys():
    text = COMPOSE_LOCAL.read_text(encoding="utf-8")
    assert "-E" in text
    assert 'REDIS_EXPORTER_CHECK_KEYS: "celery,low"' in text


def test_celery_app_sends_task_events():
    text = CELERY_APP.read_text(encoding="utf-8")
    assert '"worker_send_task_events": True' in text


def test_celery_sre_rules_component_celery():
    payload = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    names = {r["alert"] for r in payload["groups"][0]["rules"]}
    assert "GridbotCeleryWorkersZero" in names
    assert "GridbotCeleryFailureRateHigh" in names
    for rule in payload["groups"][0]["rules"]:
        assert rule["labels"]["component"] == "celery"


def test_legacy_alerts_use_flower_not_celery_tasks_failed_total():
    text = ALERTS.read_text(encoding="utf-8")
    assert "celery_tasks_failed_total" not in text
    assert "flower_events_total" in text


def test_alertmanager_celery_bypasses_telegram():
    text = AM.read_text(encoding="utf-8")
    assert "component: celery" in text
    pos_celery = text.find("component: celery")
    pos_crit = text.find("severity: critical")
    assert pos_celery != -1 and pos_crit != -1
    assert pos_celery < pos_crit


def test_celery_dashboard_round_increase_counts():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    success = next(p for p in data["panels"] if p.get("id") == 3)
    table = next(p for p in data["panels"] if p.get("id") == 12)
    assert "round(" in success["targets"][0]["expr"]
    assert "round(" in table["targets"][0]["expr"]
    assert success["fieldConfig"]["defaults"].get("decimals") == 0


def test_celery_dashboard_failure_rate_handles_empty_series():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    failure = next(p for p in data["panels"] if p.get("id") == 5)
    expr = failure["targets"][0]["expr"]
    assert "or on() vector(0)" in expr
    assert "clamp_min" in expr


def test_celery_dashboard_runtime_global_three_series():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    runtime = next(p for p in data["panels"] if p.get("id") == 8)
    exprs = [t["expr"] for t in runtime["targets"]]
    assert all("sum by (le)" in e for e in exprs)
    assert all("sum by (le, task)" not in e for e in exprs)
    assert len(exprs) == 3


def test_celery_table_colors_from_type_not_gradient_on_count():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    table = next(p for p in data["panels"] if p.get("id") == 12)
    raw = json.dumps(table["fieldConfig"])
    assert "continuous-GrYlRd" not in raw
    assert "colorBackgroundApplyFromField" in raw or "failed" in raw
