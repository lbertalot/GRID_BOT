"""Guardas de configuración: producción exige secretos y los defaults no arman live.

Los tests de defaults leen los artefactos de deploy (env.example, compose) porque
el riesgo real no está en el código sino en lo que un operador copia sin pensar.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TRUTHY = {"1", "true", "yes", "on"}


def _env_example_values() -> dict:
    values = {}
    for line in (REPO_ROOT / "env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def test_settings_production_requires_secret_key(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import app.core.config as cfg

    with pytest.raises(ValueError, match="SECRET_KEY"):
        cfg.Settings(secret_key="")


def test_settings_debug_false_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    import app.core.config as cfg

    with pytest.raises(ValueError, match="DEBUG"):
        cfg.Settings(secret_key="x", debug=True)


# ── Defaults no arman live ────────────────────────────────────────────────────


def test_effective_mode_without_any_env_is_not_armed(monkeypatch):
    """Sin ninguna variable definida el modo efectivo nunca puede ser real_armed."""
    from app.core.trading_mode import get_trading_mode_snapshot

    for var in (
        "PAPER_TRADING",
        "FORCE_REAL_MODE",
        "TRADING_ENABLED",
        "EMERGENCY_STOP",
        "BINANCE_TESTNET",
    ):
        monkeypatch.delenv(var, raising=False)

    snapshot = get_trading_mode_snapshot()
    assert snapshot["effective_mode"] != "real_armed"
    assert snapshot["force_real_mode"] is False


def test_env_example_ships_paper_defaults():
    """Copiar env.example a .env debe dejar el stack en paper, no en real."""
    values = _env_example_values()

    assert values["PAPER_TRADING"].lower() in TRUTHY, "env.example debe venir en paper"
    assert values["FORCE_REAL_MODE"].lower() not in TRUTHY, "FORCE_REAL_MODE no puede venir armado"
    assert values["EMERGENCY_STOP"].lower() not in TRUTHY


def test_env_example_has_no_real_looking_binance_keys():
    values = _env_example_values()

    for key in ("BINANCE_API_KEY", "BINANCE_SECRET_KEY"):
        value = values[key]
        assert "YOUR" in value.upper(), f"{key} debe ser placeholder, no una key real"


def test_local_compose_forces_paper_for_app_services():
    """docker-compose.local.yml es el stack paper: no puede depender del .env."""
    compose = (REPO_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")

    assert re.search(r'^\s*PAPER_TRADING:\s*"true"', compose, re.MULTILINE)
    assert not re.search(r'^\s*FORCE_REAL_MODE:\s*"?(1|true|yes|on)"?', compose, re.MULTILINE | re.IGNORECASE)


def test_default_compose_does_not_default_to_real():
    """Sin PAPER_TRADING en el entorno, docker-compose.yml debe caer en paper."""
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    paper_defaults = re.findall(r"PAPER_TRADING=\$\{PAPER_TRADING:-([^}]*)\}", compose)
    assert paper_defaults, "Se esperaba interpolación con default para PAPER_TRADING"
    for default in paper_defaults:
        assert default.lower() in TRUTHY, f"default inseguro para PAPER_TRADING: {default!r}"

    force_real_defaults = re.findall(r"FORCE_REAL_MODE=\$\{FORCE_REAL_MODE:-([^}]*)\}", compose)
    for default in force_real_defaults:
        assert default.lower() not in TRUTHY, f"FORCE_REAL_MODE armado por default: {default!r}"


def test_startup_validator_blocks_real_without_explicit_confirmation(monkeypatch):
    """PAPER_TRADING=false sin FORCE_REAL_MODE debe bloquear el arranque."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_startup", REPO_ROOT / "scripts" / "validate_startup.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.delenv("FORCE_REAL_MODE", raising=False)

    assert module.HealthChecker().check_trading_mode() is False


def test_startup_validator_blocks_contradictory_paper_and_force_real(monkeypatch):
    """FORCE_REAL_MODE anula paper: pedir los dos es config a corregir, no a arrancar."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_startup", REPO_ROOT / "scripts" / "validate_startup.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "true")

    assert module.HealthChecker().check_trading_mode() is False


def test_startup_validator_allows_paper_without_binance_credentials(monkeypatch):
    """En paper, credenciales placeholder no deben bloquear el checklist."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_startup", REPO_ROOT / "scripts" / "validate_startup.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.delenv("FORCE_REAL_MODE", raising=False)
    monkeypatch.setenv("BINANCE_API_KEY", "YOUR_BINANCE_API_KEY_HERE")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "YOUR_BINANCE_SECRET_KEY_HERE")

    checker = module.HealthChecker()
    assert checker.check_binance_env_vars() is True
    assert checker.checks_failed == 0
    assert checker.warnings, "debe quedar registrado como advertencia"
