"""B3 — Una sola SoT para daily loss: −3% (0.03).

ADR-003 / desk-policy-l0 / RFC-002: daily ≤ −3% → flat 24 h.
El path que manda en runtime es `app.core.capital_risk` (`DAILY_LOSS_LIMIT_PCT`).
Breakers, RiskManager y unified_config deben derivar el mismo número; un 0.05
hardcodeado es regresión (pre-live blocker B3).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.core.capital_risk import (
    DEFAULT_DAILY_LOSS_LIMIT_PCT,
    CapitalRiskConfig,
    daily_loss_limit_fraction,
)
from app.core.risk_manager import (
    BreakerState,
    PositionSizeParams,
    RiskManager as CoreRiskManager,
)
from app.core.auto_circuit_breaker import AutoCircuitBreaker
from app.services.risk_manager import RiskManager as ServicesRiskManager

SOT = Decimal("0.03")
SOT_FLOAT = 0.03
FORBIDDEN_LEGACY = Decimal("0.05")


def test_capital_risk_default_is_minus_three_percent():
    assert DEFAULT_DAILY_LOSS_LIMIT_PCT == "0.03"
    assert daily_loss_limit_fraction() == SOT
    cfg = CapitalRiskConfig.from_env({})
    assert cfg.daily_loss_limit_pct == SOT
    assert cfg.daily_loss_limit_pct != FORBIDDEN_LEGACY


def test_daily_loss_limit_fraction_respects_env_override(monkeypatch):
    monkeypatch.setenv("DAILY_LOSS_LIMIT_PCT", "0.02")
    assert daily_loss_limit_fraction() == Decimal("0.02")


def test_unified_config_safety_limits_match_sot(tmp_path, monkeypatch):
    monkeypatch.delenv("DAILY_LOSS_LIMIT_PCT", raising=False)
    from app.core.unified_config import UnifiedConfig

    cfg_path = tmp_path / "grid_config_test.json"
    uc = UnifiedConfig(config_file=str(cfg_path))
    if not cfg_path.exists():
        uc.create_default_config()
    limits = uc.get_safety_limits()
    assert limits["max_daily_loss"] == SOT_FLOAT
    assert limits["max_daily_loss"] != 0.05


def test_unified_config_overrides_stale_json_five_percent(tmp_path, monkeypatch):
    """Aunque el JSON diga 0.05, get_safety_limits debe devolver el SoT."""
    monkeypatch.delenv("DAILY_LOSS_LIMIT_PCT", raising=False)
    import json

    from app.core.unified_config import UnifiedConfig

    cfg_path = tmp_path / "stale.json"
    cfg_path.write_text(
        json.dumps(
            {
                "_safety_limits": {
                    "max_daily_loss": 0.05,
                    "max_total_loss": 0.10,
                }
            }
        ),
        encoding="utf-8",
    )
    uc = UnifiedConfig(config_file=str(cfg_path))
    assert uc.get_safety_limits()["max_daily_loss"] == SOT_FLOAT


def test_auto_circuit_breaker_threshold_matches_sot(monkeypatch):
    monkeypatch.delenv("DAILY_LOSS_LIMIT_PCT", raising=False)
    acb = AutoCircuitBreaker(breakers=object())  # type: ignore[arg-type]
    assert acb.thresholds["max_daily_loss_pct"] == SOT_FLOAT
    assert acb.thresholds["max_daily_loss_pct"] != 0.05


def test_services_risk_manager_matches_sot(monkeypatch):
    monkeypatch.delenv("DAILY_LOSS_LIMIT_PCT", raising=False)
    rm = ServicesRiskManager()
    assert rm.max_daily_loss_percentage == SOT_FLOAT
    assert rm.max_daily_loss_percentage != 0.05


def test_core_risk_manager_cap_and_breaker_match_sot(monkeypatch):
    monkeypatch.delenv("DAILY_LOSS_LIMIT_PCT", raising=False)
    assert PositionSizeParams.__dataclass_fields__["cap_daily_loss_pct"].default == SOT
    rm = CoreRiskManager()
    # 4% supera −3% SoT pero quedaba bajo el legacy 5% — debe cortar.
    rm.update_metrics(daily_loss=0.04, total_exposure=0.5)
    assert rm.check_circuit_breaker() == BreakerState.DANGER
    assert rm.max_loss_remaining == Decimal("0")


def test_monitoring_threshold_matches_sot(monkeypatch, tmp_path):
    monkeypatch.delenv("DAILY_LOSS_LIMIT_PCT", raising=False)
    monkeypatch.chdir(tmp_path)
    from app.core.monitoring import MonitoringSystem

    m = MonitoringSystem()
    assert m.thresholds["max_daily_loss"] == SOT_FLOAT
    assert m.thresholds["max_daily_loss"] != 0.05


def test_paper_l0_config_already_aligned():
    import json

    path = Path(__file__).resolve().parents[1] / "grid_config_paper_l0.json"
    if not path.exists():
        pytest.skip("grid_config_paper_l0.json ausente")
    data = json.loads(path.read_text(encoding="utf-8"))

    def _collect(obj, out):
        if isinstance(obj, dict):
            if "max_daily_loss" in obj:
                out.append(obj["max_daily_loss"])
            for v in obj.values():
                _collect(v, out)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item, out)

    candidates: list = []
    _collect(data, candidates)
    assert candidates, "no se encontró max_daily_loss en paper L0"
    assert all(c == SOT_FLOAT for c in candidates)


def test_no_legacy_five_percent_hardcoded_in_cut_paths():
    """Guard estático: los módulos que cortan trading no deben hardcodear 0.05."""
    root = Path(__file__).resolve().parents[1] / "app"
    files = [
        root / "core" / "unified_config.py",
        root / "core" / "auto_circuit_breaker.py",
        root / "core" / "risk_manager.py",
        root / "services" / "risk_manager.py",
        root / "core" / "monitoring.py",
    ]
    banned = (
        'max_daily_loss": 0.05',
        "max_daily_loss_pct\": 0.05",
        "max_daily_loss_percentage = 0.05",
        'cap_daily_loss_pct: Decimal = Decimal("0.05")',
        'Decimal("0.05")  # 5%',
        '"max_daily_loss": 0.05',
    )
    for path in files:
        text = path.read_text(encoding="utf-8")
        for needle in banned:
            assert needle not in text, f"legacy 5% en {path.name}: {needle!r}"
