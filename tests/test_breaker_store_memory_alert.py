"""Contrato alerta breaker store memory (Ola 1 recreate no wipe).

Paper-only. PROMOTE_LIVE: NO.
"""

from pathlib import Path

import yaml

RULES = (
    Path(__file__).resolve().parents[1]
    / "docker/prometheus/rules/paper_obs_p0_rules.yml"
)


def test_breaker_store_memory_alert_present():
    data = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    names = [r["alert"] for g in data["groups"] for r in g["rules"]]
    assert "BreakerStoreFallbackMemory" in names
    raw = RULES.read_text(encoding="utf-8")
    assert "breaker_store_backend" in raw
    assert 'backend="memory"' in raw
    assert "paper_consecutive_losses" in raw
