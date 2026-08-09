"""Cobertura paper-safe de app.api.optimized_routes (≥85% líneas).

Router huérfano: se monta en FastAPI de test; mock de grid manager / Binance / telegram.
No toca grid_config_paper_l0.json ni USE_REAL_BINANCE.
"""

from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("USE_REAL_BINANCE", "0")
os.environ.setdefault("PAPER_TRADING", "true")
os.environ.setdefault("FORCE_REAL_MODE", "false")
os.environ.setdefault("TRADING_ENABLED", "false")

from app.api import optimized_routes as opt


def _asset(symbol: str = "BTCUSDT", active: bool = True):
    return SimpleNamespace(symbol=symbol, is_active=active)


def _fake_manager(*, with_history: bool = False):
    mgr = MagicMock()
    mgr.config = SimpleNamespace(
        assets={"BTCUSDT": _asset("BTCUSDT", True), "ETHUSDT": _asset("ETHUSDT", False)}
    )
    mgr.config_file_path = "grid_config_optimized.json"
    mgr.trading_history = []
    if with_history:
        mgr.trading_history = [
            SimpleNamespace(timestamp=datetime(2026, 1, 1, 12, 0, 0))
        ]
    mgr.reload_configuration = AsyncMock(return_value=True)
    mgr.save_configuration = AsyncMock(return_value=True)
    mgr.execute_grid_trading_cycle = MagicMock()
    mgr.get_trading_statistics = MagicMock(return_value={"total_trades": 0})
    mgr.update_asset_config = MagicMock(return_value=True)
    mgr.get_asset_balances = AsyncMock(return_value={"BTCUSDT": 0.1})
    mgr.get_current_prices = AsyncMock(return_value={"BTCUSDT": 50000.0})
    return mgr


@pytest.fixture
def paper_env(monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("EMERGENCY_STOP", "false")


@pytest.fixture
def client(paper_env, monkeypatch):
    mgr = _fake_manager(with_history=True)
    monkeypatch.setattr(opt, "grid_manager", mgr)
    monkeypatch.setattr(opt, "send_telegram_alert", MagicMock())

    app = FastAPI()
    app.include_router(opt.router)
    app.dependency_overrides[opt.get_grid_manager] = lambda: mgr
    with TestClient(app) as c:
        c._mgr = mgr  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_get_grid_manager_503_when_uninitialized(paper_env, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(opt, "grid_manager", None)
    with pytest.raises(HTTPException) as ei:
        await opt.get_grid_manager()
    assert ei.value.status_code == 503


def test_status_with_history(client):
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "operational"
    assert body["active_assets"] == 1
    assert body["total_assets"] == 2
    assert body["last_trading_cycle"] is not None


def test_status_without_history(paper_env, monkeypatch):
    mgr = _fake_manager(with_history=False)
    monkeypatch.setattr(opt, "grid_manager", mgr)
    app = FastAPI()
    app.include_router(opt.router)
    app.dependency_overrides[opt.get_grid_manager] = lambda: mgr
    with TestClient(app) as c:
        r = c.get("/api/v1/status")
    assert r.status_code == 200
    assert r.json()["last_trading_cycle"] is None


def test_status_error_500(paper_env, monkeypatch):
    mgr = MagicMock()
    type(mgr).config = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(opt, "grid_manager", mgr)
    app = FastAPI()
    app.include_router(opt.router)
    app.dependency_overrides[opt.get_grid_manager] = lambda: mgr
    with TestClient(app) as c:
        r = c.get("/api/v1/status")
    assert r.status_code == 500


def test_config_reload_success(client):
    r = client.post("/api/v1/config/reload", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    client._mgr.reload_configuration.assert_awaited()


def test_config_reload_custom_path_and_failure(client):
    client._mgr.reload_configuration = AsyncMock(return_value=False)
    r = client.post(
        "/api/v1/config/reload", json={"config_file_path": "custom.json"}
    )
    assert r.status_code == 500
    assert "Failed to reload" in r.json()["detail"]


def test_config_reload_exception(client):
    client._mgr.reload_configuration = AsyncMock(side_effect=RuntimeError("io"))
    r = client.post("/api/v1/config/reload", json={})
    assert r.status_code == 500
    assert "Error reloading" in r.json()["detail"]


def test_restart_success_uses_existing_path(client, monkeypatch):
    new_mgr = _fake_manager()
    monkeypatch.setattr(
        opt, "create_optimized_grid_manager", AsyncMock(return_value=new_mgr)
    )
    r = client.post("/api/v1/grid_manager/restart")
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert opt.grid_manager is new_mgr


@pytest.mark.asyncio
async def test_restart_default_path_when_no_manager(paper_env, monkeypatch):
    monkeypatch.setattr(opt, "grid_manager", None)
    new_mgr = _fake_manager()
    create = AsyncMock(return_value=new_mgr)
    monkeypatch.setattr(opt, "create_optimized_grid_manager", create)
    result = await opt.restart_grid_manager()
    assert result["status"] == "success"
    assert create.await_args.args[0] == "grid_config_optimized.json"
    assert opt.grid_manager is new_mgr


def test_restart_failure_none(client, monkeypatch):
    monkeypatch.setattr(
        opt, "create_optimized_grid_manager", AsyncMock(return_value=None)
    )
    r = client.post("/api/v1/grid_manager/restart")
    assert r.status_code == 500
    assert "Failed to restart" in r.json()["detail"]


def test_restart_exception(client, monkeypatch):
    monkeypatch.setattr(
        opt,
        "create_optimized_grid_manager",
        AsyncMock(side_effect=RuntimeError("create")),
    )
    r = client.post("/api/v1/grid_manager/restart")
    assert r.status_code == 500


def test_trading_cycle(client):
    r = client.post("/api/v1/trading/cycle", json={"symbols": ["BTCUSDT"]})
    assert r.status_code == 200
    assert r.json()["requested_symbols"] == ["BTCUSDT"]


def test_trading_cycle_all_symbols(client):
    r = client.post("/api/v1/trading/cycle", json={})
    assert r.status_code == 200
    assert r.json()["requested_symbols"] == "all"


def test_trading_statistics(client):
    r = client.get("/api/v1/trading/statistics")
    assert r.status_code == 200
    assert r.json()["total_trades"] == 0


def test_trading_statistics_error(client):
    client._mgr.get_trading_statistics.side_effect = RuntimeError("stats")
    r = client.get("/api/v1/trading/statistics")
    assert r.status_code == 500


def test_update_asset_validation_empty(client):
    r = client.put("/api/v1/assets/BTCUSDT", json={})
    assert r.status_code == 400
    assert "No valid update" in r.json()["detail"]


def test_update_asset_pydantic_validation(client):
    r = client.put("/api/v1/assets/BTCUSDT", json={"grids": 1})
    assert r.status_code == 422


def test_update_asset_success(client):
    r = client.put(
        "/api/v1/assets/BTCUSDT",
        json={"min_price": 100.0, "max_price": 200.0, "grids": 5, "is_active": True},
    )
    assert r.status_code == 200
    assert r.json()["symbol"] == "BTCUSDT"


def test_update_asset_not_found(client):
    client._mgr.update_asset_config.return_value = False
    r = client.put("/api/v1/assets/FOOUSDT", json={"quantity": 0.01})
    assert r.status_code == 404


def test_update_asset_unexpected_error(client):
    client._mgr.update_asset_config.side_effect = RuntimeError("db")
    r = client.put("/api/v1/assets/BTCUSDT", json={"quantity": 0.01})
    assert r.status_code == 500


def test_balances_and_prices(client):
    rb = client.get("/api/v1/assets/balances")
    assert rb.status_code == 200
    assert "balances" in rb.json()
    rp = client.get("/api/v1/assets/prices")
    assert rp.status_code == 200
    assert rp.json()["prices"]["BTCUSDT"] == 50000.0


def test_balances_error(client):
    client._mgr.get_asset_balances = AsyncMock(side_effect=RuntimeError("bal"))
    assert client.get("/api/v1/assets/balances").status_code == 500


def test_prices_error(client):
    client._mgr.get_current_prices = AsyncMock(side_effect=RuntimeError("px"))
    assert client.get("/api/v1/assets/prices").status_code == 500


def test_config_save_success_and_fail(client):
    r = client.post("/api/v1/config/save")
    assert r.status_code == 200
    client._mgr.save_configuration = AsyncMock(return_value=False)
    r2 = client.post("/api/v1/config/save", params={"filepath": "x.json"})
    assert r2.status_code == 500


def test_config_save_exception(client):
    client._mgr.save_configuration = AsyncMock(side_effect=RuntimeError("save"))
    assert client.post("/api/v1/config/save").status_code == 500


def test_emergency_stop_and_resume(client, monkeypatch):
    alert = MagicMock()
    monkeypatch.setattr(opt, "send_telegram_alert", alert)
    r = client.post("/api/v1/emergency/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "stopped"
    assert alert.called
    for a in client._mgr.config.assets.values():
        assert a.is_active is False

    r2 = client.post("/api/v1/emergency/resume")
    assert r2.status_code == 200
    assert r2.json()["active_assets"] == 2


def test_emergency_stop_error(client):
    broken_cfg = MagicMock()
    type(broken_cfg).assets = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("assets"))
    )
    client._mgr.config = broken_cfg
    assert client.post("/api/v1/emergency/stop").status_code == 500


def test_emergency_resume_error(client):
    broken_cfg = MagicMock()
    type(broken_cfg).assets = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("assets"))
    )
    client._mgr.config = broken_cfg
    assert client.post("/api/v1/emergency/resume").status_code == 500


def test_paper_guard_rejects_live_mutations(client, monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    r = client.post("/api/v1/trading/cycle", json={})
    assert r.status_code == 403
    assert "Live mutations rejected" in r.json()["detail"]
    r2 = client.post("/api/v1/emergency/stop")
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_initialize_grid_manager_paths(paper_env, monkeypatch):
    monkeypatch.setattr(opt, "grid_manager", None)
    monkeypatch.setattr(
        opt, "create_optimized_grid_manager", AsyncMock(return_value=_fake_manager())
    )
    await opt.initialize_grid_manager()
    assert opt.grid_manager is not None

    monkeypatch.setattr(
        opt, "create_optimized_grid_manager", AsyncMock(return_value=None)
    )
    await opt.initialize_grid_manager()
    assert opt.grid_manager is None

    monkeypatch.setattr(
        opt,
        "create_optimized_grid_manager",
        AsyncMock(side_effect=RuntimeError("init")),
    )
    await opt.initialize_grid_manager()  # no raise


@pytest.mark.asyncio
async def test_startup_shutdown_events(paper_env, monkeypatch):
    monkeypatch.setattr(
        opt, "create_optimized_grid_manager", AsyncMock(return_value=_fake_manager())
    )
    await opt.startup_event()
    assert opt.grid_manager is not None
    await opt.shutdown_event()
    assert opt.grid_manager is None
