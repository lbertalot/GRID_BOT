"""Contrato GridBotTickStalled — Flower, no absent(cycle_phase_timestamp).

Paper-only. PROMOTE_LIVE: NO.
"""

from pathlib import Path

import yaml

RULES = (
    Path(__file__).resolve().parents[1]
    / "docker/prometheus/rules/trading_cycle_rules.yml"
)


def test_tick_stalled_uses_flower_tick_succeeded():
    raw = RULES.read_text(encoding="utf-8")
    assert "trading_cycle_tick" in raw
    assert "flower_events_total" in raw
    data = yaml.safe_load(raw)
    stalled = next(
        r
        for g in data["groups"]
        for r in g["rules"]
        if r.get("alert") == "GridBotTickStalled"
    )
    expr = stalled["expr"]
    assert "absent(" not in expr
    assert "cycle_phase_timestamp" not in expr
    assert "gridbot-celery" in expr
    assert "trading_cycle_tick" in expr
