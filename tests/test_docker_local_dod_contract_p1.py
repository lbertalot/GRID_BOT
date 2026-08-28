"""Contract tests: DoD Docker local (markdown + compose defaults). No network."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_docker_local_dod_checklist_exists() -> None:
    doc = REPO_ROOT / "Docs" / "DOCKER_LOCAL_DOD_CHECKLIST.md"
    assert doc.is_file()
    text = _read(doc)
    assert len(text) > 400
    lower = text.lower()
    assert "docker-compose.local.yml" in lower or "compose local" in lower
    assert "/health" in lower or "health" in lower
    assert "paper_trading" in lower
    assert "trading_enabled" in lower


def test_compose_local_safe_trading_defaults() -> None:
    compose_path = REPO_ROOT / "docker-compose.local.yml"
    assert compose_path.is_file()
    text = _read(compose_path)
    lower = text.lower()
    assert 'paper_trading: "true"' in lower or "paper_trading: 'true'" in lower
    assert 'trading_enabled: "false"' in lower or "trading_enabled: 'false'" in lower


def test_compose_local_declares_migrate_before_api() -> None:
    """migrate aparece antes que api (orden de servicios en el archivo)."""
    compose_path = REPO_ROOT / "docker-compose.local.yml"
    text = _read(compose_path)
    idx_migrate = text.find("\n  migrate:")
    idx_api = text.find("\n  api:")
    assert idx_migrate != -1 and idx_api != -1
    assert idx_migrate < idx_api


def test_compose_beat_pidfile_not_on_persistent_data_volume() -> None:
    """Schedule sí en /app/data; pidfile en /tmp (recreate no crash-loop)."""
    text = _read(REPO_ROOT / "docker-compose.local.yml")
    assert "--schedule /app/data/celerybeat-schedule" in text
    assert "--pidfile=/tmp/celerybeat.pid" in text
    assert "--pidfile=/app/data/celerybeat.pid" not in text
    assert "/tmp/celerybeat.pid" in text
    assert "test -f /app/data/celerybeat-schedule" not in text


def test_agents_links_docker_dod_checklist() -> None:
    agents = _read(REPO_ROOT / "AGENTS.md")
    assert "DOCKER_LOCAL_DOD_CHECKLIST.md" in agents
