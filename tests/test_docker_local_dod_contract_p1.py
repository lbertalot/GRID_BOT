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


def test_compose_local_n10_not_trial_overlay() -> None:
    """Tras NO-GO SI 5×15 intento 3: compose apunta a N10, sin PAPER_TRIAL_*."""
    text = _read(REPO_ROOT / "docker-compose.local.yml")
    assert "GRID_CONFIG_FILE: grid_config_paper_l0.json" in text
    assert "GRID_CONFIG_FILE: grid_config_paper_l0_trial_5x15.json" not in text
    assert "PAPER_TRIAL_STARTED_AT" not in text
    assert "PAPER_TRIAL_STREAK_THRESHOLD" not in text
    assert 'PAPER_EARLY_STREAK_WARN: "3"' in text


def test_compose_local_safe_trading_defaults() -> None:
    compose_path = REPO_ROOT / "docker-compose.local.yml"
    assert compose_path.is_file()
    text = _read(compose_path)
    lower = text.lower()
    assert 'paper_trading: "true"' in lower or "paper_trading: 'true'" in lower
    # Fail-closed default; .env puede encender paper sin que el YAML pinée false.
    assert (
        'trading_enabled: "${trading_enabled:-false}"' in lower
        or 'trading_enabled: "false"' in lower
        or "trading_enabled: 'false'" in lower
    )


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
    # Restart del mismo contenedor deja pidfile en /tmp con PID 1 vivo → exit 73.
    assert "rm -f /tmp/celerybeat.pid" in text


def test_compose_cadvisor_does_not_bind_dmi_over_sysfs() -> None:
    """sysfs no admite mkdir DMI; un bind a /sys/class/dmi rompe el start en Desktop."""
    compose = _read(REPO_ROOT / "docker-compose.local.yml")
    assert "/sys/class/dmi" not in compose
    readme = _read(REPO_ROOT / "docker" / "cadvisor" / "README.md")
    assert "gce.go" in readme
    assert "product_name" in readme


def test_agents_links_docker_dod_checklist() -> None:
    agents = _read(REPO_ROOT / "AGENTS.md")
    assert "DOCKER_LOCAL_DOD_CHECKLIST.md" in agents
