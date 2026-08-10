"""COV-2.3 — config_routes + strategies.py paper contracts.

Paper-only · no live · PROMOTE_LIVE: NO.
No escribe ``grid_config_paper_l0.json`` ni invalida hash de ventana.
Mutaciones peligrosas solo contra mock de ``get_config``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import config_routes as cr
from app.api import strategies as strat


@pytest.fixture
def mock_cfg():
    cfg = MagicMock(name="unified_config")
    cfg.get_config_summary.return_value = {"mode": "paper", "assets": 2}
    cfg.get_all_assets.return_value = {
        "BTCUSDT": {"is_active": True, "grids": 10, "quantity": 0.001}
    }
    cfg.get_asset_config.side_effect = lambda s: (
        {"is_active": True, "grids": 10} if s.upper() == "BTCUSDT" else None
    )
    cfg.get_safety_limits.return_value = {"max_daily_loss": 0.03}
    cfg.get_monitoring_settings.return_value = {"interval_sec": 60}
    cfg.get_system_settings.return_value = {"paper_trading": True}
    cfg.validate_config.return_value = (True, [])
    cfg.create_backup.return_value = "/tmp/fake-backup.json"
    return cfg


@pytest.fixture
def config_client(paper_env, mock_cfg):
    app = FastAPI()
    app.include_router(cr.router)
    with patch.object(cr, "get_config", return_value=mock_cfg):
        yield TestClient(app), mock_cfg


@pytest.fixture
def strat_client(paper_env):
    app = FastAPI()
    app.include_router(strat.router)
    return TestClient(app)


# ── config GETs (paper-honest, sin edge claim) ───────────────────────────────


def test_config_summary_and_assets_reads(config_client):
    client, cfg = config_client
    s = client.get("/api/config/summary")
    assert s.status_code == 200
    assert s.json()["mode"] == "paper"

    assets = client.get("/api/config/assets")
    assert assets.status_code == 200
    assert assets.json()[0]["symbol"] == "BTCUSDT"

    one = client.get("/api/config/assets/BTCUSDT")
    assert one.status_code == 200
    assert one.json()["is_active"] is True

    missing = client.get("/api/config/assets/NOPE")
    assert missing.status_code == 404


def test_config_safety_monitoring_system_gets(config_client):
    client, _ = config_client
    assert client.get("/api/config/safety").status_code == 200
    assert client.get("/api/config/monitoring").status_code == 200
    assert client.get("/api/config/system").json()["paper_trading"] is True


def test_config_asset_mutations_use_mock_only(config_client):
    """Mutaciones no tocan disco L0 — solo métodos del mock."""
    client, cfg = config_client

    tog = client.post("/api/config/assets/BTCUSDT/toggle", json={"is_active": False})
    assert tog.status_code == 200
    assert tog.json()["is_active"] is False
    cfg.update_asset_config.assert_called()

    upd = client.put("/api/config/assets/BTCUSDT", json={"grids": 12})
    assert upd.status_code == 200
    cfg.update_asset_config.assert_called()

    cfg.get_asset_config.side_effect = lambda s: None
    add = client.post(
        "/api/config/assets",
        json={"symbol": "ETHUSDT", "min_price": 100, "max_price": 5000, "grids": 8},
    )
    assert add.status_code == 200
    cfg.add_asset.assert_called_once()

    cfg.get_asset_config.side_effect = lambda s: {"is_active": True}
    rem = client.delete("/api/config/assets/ETHUSDT")
    assert rem.status_code == 200
    cfg.remove_asset.assert_called_once_with("ETHUSDT")


def test_config_add_asset_validation(config_client):
    client, cfg = config_client
    assert client.post("/api/config/assets", json={}).status_code == 400
    cfg.get_asset_config.side_effect = lambda s: {"is_active": True}
    assert (
        client.post("/api/config/assets", json={"symbol": "BTCUSDT"}).status_code
        == 409
    )


def test_config_safety_monitoring_system_updates(config_client):
    client, cfg = config_client
    bad = client.put("/api/config/safety", json={"max_daily_loss": 1})
    assert bad.status_code == 400

    ok = client.put(
        "/api/config/safety",
        json={
            "max_daily_loss": 3,
            "max_total_loss": 10,
            "max_trade_loss": 1,
            "max_consecutive_losses": 5,
            "min_balance": 100,
        },
    )
    assert ok.status_code == 200
    cfg.update_safety_limits.assert_called_once()

    mon = client.put("/api/config/monitoring", json={"interval_sec": 30})
    assert mon.status_code == 200
    cfg.update_monitoring_settings.assert_called_once()

    sys = client.put("/api/config/system", json={"log_level": "INFO"})
    assert sys.status_code == 200
    cfg.update_system_settings.assert_called_once()


def test_config_trading_flags_via_mock_not_env(config_client, monkeypatch):
    """enable/disable trading y paper solo invocan mock — env paper intacto."""
    import os

    client, cfg = config_client
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("TRADING_ENABLED", "false")

    assert client.post("/api/config/enable-trading").status_code == 200
    cfg.enable_trading.assert_called_once()
    assert client.post("/api/config/disable-trading").status_code == 200
    cfg.disable_trading.assert_called_once()
    assert client.post("/api/config/enable-paper-trading").status_code == 200
    cfg.enable_paper_trading.assert_called_once()
    assert client.post("/api/config/disable-paper-trading").status_code == 200
    cfg.disable_paper_trading.assert_called_once()

    assert os.environ.get("PAPER_TRADING", "").lower() in {"1", "true", "yes"}
    assert not os.environ.get("FORCE_REAL_MODE", "")


def test_config_validate_backup_reset(config_client):
    client, cfg = config_client
    v = client.post("/api/config/validate")
    assert v.status_code == 200
    assert v.json()["valid"] is True

    b = client.post("/api/config/backup")
    assert b.status_code == 200
    assert b.json()["backup_file"] == "config_backup.json"

    r = client.post("/api/config/reset")
    assert r.status_code == 200
    cfg.create_default_config.assert_called_once()


def test_config_reads_error_500(paper_env):
    app = FastAPI()
    app.include_router(cr.router)
    with patch.object(cr, "get_config", side_effect=RuntimeError("boom")):
        client = TestClient(app)
        assert client.get("/api/config/summary").status_code == 500
        assert client.get("/api/config/assets").status_code == 500
        assert client.get("/api/config/safety").status_code == 500


def test_paper_summary_reset_buy_sell_mocked(paper_env):
    app = FastAPI()
    app.include_router(cr.router)
    client = TestClient(app)

    with patch(
        "app.core.paper_trading.get_paper_portfolio_summary",
        return_value={"equity": "1000", "paper": True},
    ):
        s = client.get("/api/config/paper/summary")
    assert s.status_code == 200
    assert s.json()["paper"] is True

    with patch(
        "app.core.paper_trading.paper_trading_system"
    ) as pts:
        r = client.post("/api/config/paper/reset?balance=1000")
    assert r.status_code == 200
    pts.reset_paper_trading.assert_called_once_with(new_balance=1000.0)

    with patch(
        "app.core.paper_trading.place_paper_buy_order",
        return_value={"id": "b1", "side": "BUY"},
    ), patch(
        "app.core.paper_trading.place_paper_sell_order",
        return_value={"id": "s1", "side": "SELL"},
    ):
        buy = client.post(
            "/api/config/paper/buy",
            json={"symbol": "BTCUSDT", "quantity": 0.001, "price": 50000},
        )
        sell = client.post(
            "/api/config/paper/sell",
            json={"symbol": "BTCUSDT", "quantity": 0.001, "price": 51000},
        )
    assert buy.status_code == 200 and buy.json()["order"]["side"] == "BUY"
    assert sell.status_code == 200 and sell.json()["order"]["side"] == "SELL"


# ── strategies.py (histórico inyectado → cero Binance) ───────────────────────


def test_strategies_with_injected_history(strat_client):
    hist = [100 + i * 0.5 for i in range(30)]
    balances = {"USDT": 1000.0, "BTC": 0.01}
    body = {
        "symbol": "BTCUSDT",
        "price_history": hist,
        "balances": balances,
        "params": {},
    }
    for path in (
        "/strategy/trailing_stop",
        "/strategy/scalping",
        "/strategy/rsi_macd",
    ):
        r = strat_client.post(path, json=body)
        assert r.status_code == 200, path
        assert "action" in r.json()


def test_strategies_fetch_history_error(strat_client):
    with patch.object(
        strat, "get_price_history", side_effect=RuntimeError("no network")
    ):
        for path in (
            "/strategy/trailing_stop",
            "/strategy/scalping",
            "/strategy/rsi_macd",
        ):
            r = strat_client.post(path, json={"balances": {"USDT": 1}, "params": {}})
            assert r.status_code == 400, path
            assert "Binance" in r.json()["detail"]
        bt = strat_client.post(
            "/strategy/backtest?strategy=scalping",
            json={"balances": {"USDT": 1}},
        )
        assert bt.status_code == 400


def test_strategy_backtest_injected_and_short_history(strat_client):
    hist = [100.0 + i for i in range(15)]
    r = strat_client.post(
        "/strategy/backtest?strategy=scalping",
        json={
            "price_history": hist,
            "balances": {"USDT": 100},
            "params": {},
        },
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1

    short = strat_client.post(
        "/strategy/backtest?strategy=scalping",
        json={"price_history": [1, 2, 3], "balances": {"USDT": 1}},
    )
    assert short.status_code == 400


def test_get_price_history_uses_client_klines():
    mock_client = MagicMock()
    mock_client.get_klines.return_value = [[0, 0, 0, 0, "100.5"]] * 3
    with patch.object(strat, "Client", return_value=mock_client):
        prices = strat.get_price_history("btcusdt", "1h", 3)
    assert prices == [100.5, 100.5, 100.5]
    mock_client.get_klines.assert_called_once()
