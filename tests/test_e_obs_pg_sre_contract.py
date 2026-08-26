"""Contrato E-OBS-PG-SRE — dash Postgres + reglas Prom + compose.

Paper-only. Sin red a Binance. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "docker/grafana/dashboards/gridbot-pg-sre.json"
RULES = ROOT / "docker/prometheus/rules/gridbot_postgres_sre.yml"
COMPOSE_LOCAL = ROOT / "docker-compose.local.yml"
AM = ROOT / "docker/alertmanager/alertmanager.yml"


def test_pg_sre_dashboard_uid_and_refresh():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    assert data["uid"] == "gridbot-pg-sre"
    assert data["refresh"] == "15s"
    assert data["time"]["from"] == "now-6h"
    titles = [p.get("title") for p in data["panels"]]
    assert "Cache hit ratio" in titles
    assert "Top 5 slow queries" in titles
    assert "Tasa inserción trades" in titles


def test_pg_sre_dashboard_no_count_star_on_core_tables():
    raw = DASH.read_text(encoding="utf-8").lower()
    assert "count(*) from trades" not in raw
    assert "count(*) from asset_limits" not in raw
    assert "count(*) from grid_config" not in raw


def test_postgresql_overview_legacy_removed():
    legacy = ROOT / "docker/grafana/dashboards/postgresql-overview.json"
    assert not legacy.exists(), "postgresql-overview.json legacy debe estar eliminado"


def test_prometheus_pg_rules_component_postgres_not_ceo():
    payload = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    alerts = payload["groups"][0]["rules"]
    names = {r["alert"] for r in alerts}
    assert "GridbotPgDown" in names
    assert "GridbotPgCacheHitLow" in names
    assert "GridbotPgDeadlocks" in names
    for rule in alerts:
        assert rule["labels"]["component"] == "postgres"


def test_compose_local_preloads_pg_stat_statements():
    text = COMPOSE_LOCAL.read_text(encoding="utf-8")
    assert "shared_preload_libraries=pg_stat_statements" in text
    assert "track_io_timing=on" in text


def test_pg_sre_slow_queries_excludes_catalog_noise():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    panel = next(p for p in data["panels"] if p.get("id") == 5)
    sql = panel["targets"][0]["rawSql"].lower()
    assert "%pg_catalog%" in sql
    assert "show|set|begin" in sql or "grant|revoke|alter|create|drop" in sql
    assert "%pg_settings%" in sql
    assert "%pg_ls_waldir%" in sql
    # DML-only: business queries, no migration DDL
    assert "select|insert|update|delete|with" in sql.replace("\\", "")
    assert "grant|revoke|alter|create|drop" in sql.replace("\\", "")


def test_pg_sre_slow_queries_dml_allowlist_excludes_ddl():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    panel = next(p for p in data["panels"] if p.get("id") == 5)
    sql = panel["targets"][0]["rawSql"]
    assert r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH)\b" in sql or (
        "SELECT|INSERT|UPDATE|DELETE|WITH" in sql
    )
    for ddl in ("GRANT", "ALTER", "CREATE", "DROP"):
        assert ddl in sql


def test_pg_sre_connections_split_active_idle():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    panel = next(p for p in data["panels"] if p.get("id") == 3)
    exprs = [t["expr"] for t in panel["targets"]]
    assert any('state="active"' in e for e in exprs)
    assert any('state="idle"' in e for e in exprs)
    assert panel["fieldConfig"]["defaults"]["max"] == 100


def test_pg_sre_dead_tuples_fixed_max_scale():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    panel = next(p for p in data["panels"] if p.get("id") == 10)
    defaults = panel["fieldConfig"]["defaults"]
    assert defaults["max"] == 10000
    assert defaults["min"] == 0
    steps = defaults["thresholds"]["steps"]
    assert steps[1]["value"] == 2000
    assert steps[2]["value"] == 5000


def test_pg_sre_trade_insert_rate_uses_rate_5m_and_timestamp():
    data = json.loads(DASH.read_text(encoding="utf-8"))
    panel = next(p for p in data["panels"] if p.get("id") == 12)
    prom = panel["targets"][0]["expr"]
    assert "rate(" in prom and "[5m]" in prom
    assert "n_tup_ins" in prom
    sql = panel["targets"][1]["rawSql"]
    assert "$__timeGroup(timestamp" in sql
    assert "$__timeFilter(timestamp)" in sql


def test_alertmanager_postgres_bypasses_telegram():
    text = AM.read_text(encoding="utf-8")
    assert "component: postgres" in text
    pos_pg = text.find("component: postgres")
    pos_crit = text.find("severity: critical")
    assert pos_pg != -1 and pos_crit != -1
    assert pos_pg < pos_crit
