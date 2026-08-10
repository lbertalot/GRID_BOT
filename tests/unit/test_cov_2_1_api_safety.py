"""COV-2.1 — API safety contracts (gate/breakers/risk/capital/system).

Paper-only · no live · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def paper_client(paper_env):
    from app.api.system_routes import router as system_router

    app = FastAPI()
    app.include_router(system_router)
    return TestClient(app)


def test_gate_live_status_is_read_only_and_unsigned_by_default(paper_env):
    from app.api.gate_routes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/api/gates/live-status")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"timestamp", "gate"}
    gate = body["gate"]
    assert gate["signed"] is False
    assert gate["checklist_complete"] is False
    assert client.post("/api/gates/live-status").status_code == 405


def test_breakers_summary_and_status_aliases_paper_safe(paper_env):
    from app.api import breakers_routes as br

    mock_cb = MagicMock()
    mock_cb.get_all_breakers_status.return_value = {
        "critical_mode": False,
        "active_breakers": [],
        "total_active": 0,
        "breakers": {},
    }
    br.router.breakers = mock_cb
    br.api_router.breakers = mock_cb

    app = FastAPI()
    app.include_router(br.router)
    app.include_router(br.api_router)
    client = TestClient(app)

    try:
        with patch(
            "app.api.breakers_routes.get_breaker_visibility_snapshot",
            return_value={
                "generated_at": "2026-08-10T00:00:00Z",
                "any_open": False,
                "emergency_stop": False,
                "open_count": 0,
                "breakers": [],
            },
        ):
            for path in (
                "/breakers/summary",
                "/api/breakers/summary",
                "/breakers/status",
                "/api/breakers/status",
            ):
                assert client.get(path).status_code == 200

        mock_cb.get_all_breakers_status.side_effect = RuntimeError("boom")
        assert client.get("/breakers/summary").status_code == 500
        with patch(
            "app.api.breakers_routes.get_breaker_visibility_snapshot",
            side_effect=RuntimeError("boom"),
        ):
            assert client.get("/api/breakers/status").status_code == 500
    finally:
        for attr in ("breakers",):
            for target in (br.router, br.api_router):
                if hasattr(target, attr):
                    delattr(target, attr)


def test_system_health_endpoints_expose_paper_mode(paper_client):
    for path in ("/", "/health", "/health/trading-mode", "/health/readiness"):
        r = paper_client.get(path)
        assert r.status_code == 200
        body = r.json()
        trading = body.get("trading") or {}
        assert trading.get("effective_mode") == "paper"
        assert trading.get("paper_trading") is True
        assert trading.get("force_real_mode") is False

    live = paper_client.get("/health/liveness")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"


def test_orphan_risk_routes_all_mutators_410_with_auth(paper_env, monkeypatch):
    monkeypatch.setenv("API_KEY", "cov-21-orphan-key")
    from app.api.risk_routes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    headers = {"Authorization": "Bearer cov-21-orphan-key"}

    paths_post = [
        "/api/v2/risk/emergency-stop",
        "/api/v2/risk/reset-emergency-stop",
        "/api/v2/risk/update-metrics",
        "/api/v2/risk/apply-regime-filter",
        "/api/v2/risk/calculate-position-size",
        "/api/v2/risk/calculate-trailing-stop",
        "/api/v2/risk/update-trailing-stop",
    ]
    for path in paths_post:
        assert client.post(path, headers=headers).status_code == 410

    for path in (
        "/api/v2/risk/status",
        "/api/v2/risk/circuit-breaker-status",
        "/api/v2/risk/trailing-stops",
    ):
        assert client.get(path, headers=headers).status_code == 410

    # sin auth → 401 (no ejecuta stop)
    assert client.post("/api/v2/risk/emergency-stop").status_code == 401


def test_capital_status_evaluation_error_500(paper_env):
    from app.api import capital_risk_routes as mod
    from app.core.capital_risk import CapitalRiskInputError, EquitySnapshot

    app = FastAPI()
    app.include_router(mod.router)

    def _equity():
        return EquitySnapshot(equity=Decimal("1000"), equity_prev_eod=None, source="test")

    def _ops():
        return MagicMock()

    app.dependency_overrides[mod.get_equity_provider] = lambda: _equity
    app.dependency_overrides[mod.get_ops_provider] = lambda: _ops

    with patch(
        "app.api.capital_risk_routes.evaluate_capital_risk",
        side_effect=CapitalRiskInputError("bad input"),
    ):
        client = TestClient(app)
        r = client.get("/api/risk/capital-status")
    assert r.status_code == 500
    body = r.json()
    assert body["success"] is False
    assert body["error"] == "capital_risk_evaluation_failed"
