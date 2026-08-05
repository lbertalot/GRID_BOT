"""A2 — Security audit post PR #47: guards en order_market_*, orphan risk_routes, defaults."""

from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_trading_mode_defaults_fail_closed(monkeypatch):
    """Sin env explícito: paper + trading off (no armar live por omisión)."""
    for key in (
        "PAPER_TRADING",
        "FORCE_REAL_MODE",
        "TRADING_ENABLED",
        "EMERGENCY_STOP",
        "BINANCE_TESTNET",
        "LIVE_GATE_PATH",
        "LIVE_GATE_DIR",
    ):
        monkeypatch.delenv(key, raising=False)

    from app.core.trading_mode import get_trading_mode_snapshot

    snap = get_trading_mode_snapshot()
    assert snap["paper_trading"] is True
    assert snap["trading_enabled"] is False
    assert snap["force_real_mode"] is False
    assert snap["effective_mode"] == "paper"


def test_orphan_risk_routes_emergency_stop_gone_with_auth(monkeypatch):
    """Si alguien cablea el router huérfano: exige auth y responde 410 (no ejecuta stop)."""
    monkeypatch.setenv("API_KEY", "test-security-post-47-key")

    from app.api.risk_routes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    unauth = client.post("/api/v2/risk/emergency-stop", params={"reason": "x"})
    assert unauth.status_code == 401

    headers = {"Authorization": "Bearer test-security-post-47-key"}
    gone = client.post(
        "/api/v2/risk/emergency-stop",
        params={"reason": "x"},
        headers=headers,
    )
    assert gone.status_code == 410
    detail = gone.json()["detail"]
    assert "Orphan" in detail or "deshabilitado" in detail


def test_binance_service_execute_blocked_when_force_real_without_gate(monkeypatch):
    """FORCE_REAL_MODE sin live gate no debe llegar a order_market_*."""
    from app.core.order_execution_guard import RealOrderBlocked
    from app.services import binance_service as bs_mod

    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    monkeypatch.delenv("LIVE_GATE_PATH", raising=False)
    monkeypatch.delenv("LIVE_GATE_DIR", raising=False)

    called = {"buy": False}

    def _buy(**_kwargs):
        called["buy"] = True
        raise AssertionError("order_market_buy no debe ejecutarse")

    svc = bs_mod.BinanceService.__new__(bs_mod.BinanceService)
    svc.simulation_mode = False
    svc.force_real_mode = True
    svc.client = type("C", (), {"order_market_buy": staticmethod(_buy)})()

    with pytest.raises(RealOrderBlocked):
        svc.execute_trading_order("BTCUSDT", "BUY", "MARKET", 0.001, price=50000.0)
    assert called["buy"] is False
