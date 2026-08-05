"""Contract tests for Passive Income P0 ops documentation and compose conventions.

Reads only local markdown/yaml; no network. See Docs/PASSIVE_INCOME_EVOLUTION_PHASED_PLAN.md §3.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_egress_runbook_exists() -> None:
    runbook = REPO_ROOT / "Docs" / "EGRESS_API_KEYS_RUNBOOK.md"
    assert runbook.is_file()
    content = _read_text(runbook)
    assert len(content) > 500


def test_egress_runbook_covers_protocol_section_keywords() -> None:
    runbook = REPO_ROOT / "Docs" / "EGRESS_API_KEYS_RUNBOOK.md"
    lower = _read_text(runbook).lower()
    assert "whitelist" in lower
    assert "nat" in lower or "egress" in lower
    assert "rotación" in lower or "rotacion" in lower or "rotaci" in lower
    assert "retiro" in lower or "withdraw" in lower
    assert "paper_trading" in lower
    assert "trading_enabled" in lower


def test_evolution_phased_plan_exists() -> None:
    plan = REPO_ROOT / "Docs" / "PASSIVE_INCOME_EVOLUTION_PHASED_PLAN.md"
    assert plan.is_file()
    assert len(_read_text(plan)) > 0


def test_agents_md_mentions_critical_trading_env_vars() -> None:
    agents = REPO_ROOT / "AGENTS.md"
    text = _read_text(agents)
    assert "PAPER_TRADING" in text
    assert "TRADING_ENABLED" in text
    assert "EMERGENCY_STOP" in text


def _compose_has_db_redis_api(text: str) -> bool:
    lower = text.lower()
    has_db = "db:" in lower or "postgres" in lower
    has_redis = "redis" in lower
    has_api_ref = (
        "api:" in lower
        or "api_dev:" in lower
        or "uvicorn" in lower
        or "fastapi" in lower
    )
    return has_db and has_redis and has_api_ref


def test_compose_local_or_main_documents_db_redis_api() -> None:
    candidates = (
        REPO_ROOT / "docker-compose.local.yml",
        REPO_ROOT / "docker-compose.yml",
    )
    contents = [p for p in candidates if p.is_file()]
    assert contents, "expected docker-compose.local.yml or docker-compose.yml"
    assert any(_compose_has_db_redis_api(_read_text(p)) for p in contents)
