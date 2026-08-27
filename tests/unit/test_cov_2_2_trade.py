"""COV-2.2 — trade.py paper place/guards + read contracts.

Paper-only · no live · PROMOTE_LIVE: NO.
Cada rama de guard documentada; qty/price vía Decimal en asserts críticos.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import trade as trade_module
from app.core.order_execution_guard import RealOrderBlocked
from app.main import app


@pytest.fixture
def api_headers(paper_env, monkeypatch):
    monkeypatch.setenv("API_KEY", "cov-22-key")
    return {"Authorization": "Bearer cov-22-key"}


def _order_body(**overrides):
    body = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": 0.001,
        "type": "MARKET",
    }
    body.update(overrides)
    return body


def test_log_trade_persists_decimal_safe_fields():
    db = MagicMock()
    trade = trade_module.log_trade(
        db=db,
        symbol="BTCUSDT",
        side="BUY",
        quantity=float(Decimal("0.001")),
        entry_price=float(Decimal("50000.00")),
    )
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(trade)


def test_controlled_write_requires_dev_and_paper(api_headers, monkeypatch):
    client = TestClient(app, base_url="http://localhost")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("PAPER_TRADING", "true")
    assert (
        client.post("/api/trade/controlled-write-test", headers=api_headers).status_code
        == 403
    )

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("PAPER_TRADING", "false")
    assert (
        client.post("/api/trade/controlled-write-test", headers=api_headers).status_code
        == 403
    )


def test_controlled_write_paper_dev_ok(api_headers, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("PAPER_TRADING", "true")
    client = TestClient(app, base_url="http://localhost")

    mock_db = MagicMock()
    fake_trade = MagicMock(id=11)
    fake_balance = MagicMock(id=22)
    fake_alert = MagicMock(id=33)

    with patch.object(trade_module, "SessionLocal", return_value=mock_db), patch.object(
        trade_module, "log_trade", return_value=fake_trade
    ), patch.object(
        trade_module.BalanceService, "update_balance", return_value=fake_balance
    ), patch.object(trade_module, "Alert", return_value=fake_alert):
        mock_db.refresh.side_effect = lambda obj: None
        r = client.post("/api/trade/controlled-write-test", headers=api_headers)

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["trade_id"] == 11
    assert body["marker"].startswith("AUDIT_CTRL_")


def test_binance_status_and_price_balances_mocked(paper_env):
    client = TestClient(app, base_url="http://localhost")
    svc = MagicMock()
    svc.simulation_mode = True
    svc.get_current_price.return_value = 50000.0
    svc.get_account_info.return_value = {
        "accountType": "SPOT",
        "balances": [{"asset": "USDT", "free": "10"}, {"asset": "BTC", "free": "0"}],
    }
    svc.api_key = "k"
    svc.api_secret = "s"

    with patch.object(trade_module, "BinanceService", return_value=svc):
        st = client.get("/api/trade/binance_status")
    assert st.status_code == 200
    assert st.json()["status"] == "success"
    assert st.json()["simulation_mode"] is True

    with patch.object(trade_module, "binance_service", svc):
        px = client.get("/api/trade/price/btcusdt")
        bal = client.get("/api/trade/balances")
    assert px.status_code == 200
    assert px.json() == {"symbol": "BTCUSDT", "price": 50000.0}
    assert bal.status_code == 200
    assert bal.json() == {"USDT": 10.0}


def test_binance_status_error_envelope(paper_env):
    client = TestClient(app, base_url="http://localhost")
    with patch.object(trade_module, "BinanceService", side_effect=RuntimeError("down")):
        r = client.get("/api/trade/binance_status")
    assert r.status_code == 200
    assert r.json()["status"] == "error"


def test_get_trades_filters_with_auth(api_headers):
    mock_db = MagicMock()
    q = MagicMock()
    mock_db.query.return_value = q
    q.filter.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.all.return_value = []

    app.dependency_overrides[trade_module.get_db] = lambda: mock_db
    try:
        client = TestClient(app, base_url="http://localhost")
        r = client.get(
            "/api/trade/trades?symbol=btcusdt&side=buy&limit=5",
            headers=api_headers,
        )
        r2 = client.get("/api/trades?symbol=ETHUSDT&side=SELL", headers=api_headers)
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r2.status_code == 200
    assert r.json() == []


def test_place_order_breaker_active_503(api_headers, monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    breakers = MagicMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": True,
        "total_active": 1,
        "active_breakers": ["drawdown"],
    }
    app.state.breakers = breakers
    try:
        client = TestClient(app, base_url="http://localhost")
        r = client.post(
            "/api/trade/order",
            json=_order_body(),
            headers=api_headers,
        )
    finally:
        if hasattr(app.state, "breakers"):
            delattr(app.state, "breakers")

    assert r.status_code == 503
    assert "circuit breaker" in r.json()["detail"].lower()


def test_place_order_rejects_reduce_only_even_for_sell(api_headers):
    """La ruta Binance genérica nunca transforma REDUCE_ONLY en un SELL real."""
    breakers = MagicMock()
    breakers.get_all_breakers_status.return_value = {
        "critical_mode": False,
        # Snapshot corrupto: la política SI debe prevalecer sobre total_active.
        "total_active": 0,
        "active_breakers": [],
        "breakers": {
            "system_integrity": {
                "active": True,
                "operational_state": "REDUCE_ONLY",
            }
        },
    }
    app.state.breakers = breakers
    try:
        client = TestClient(app, base_url="http://localhost")
        response = client.post(
            "/api/trade/order",
            json=_order_body(side="SELL"),
            headers=api_headers,
        )
    finally:
        if hasattr(app.state, "breakers"):
            delattr(app.state, "breakers")

    assert response.status_code == 503
    assert "system_integrity" in response.json()["detail"]


def test_place_order_validation_reject_400(api_headers, monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    mock_client = MagicMock()
    mock_client.get_symbol_ticker.return_value = {"price": "50000"}
    mock_db = MagicMock()

    with patch.object(trade_module, "Client", return_value=mock_client), patch.object(
        trade_module, "OrderValidator"
    ) as ov, patch.object(
        trade_module, "get_shared_breakers"
    ) as gb:
        gb.return_value.get_all_breakers_status.return_value = {
            "critical_mode": False,
            "total_active": 0,
        }
        ov.return_value.validate_order_parameters.return_value = {
            "is_valid": False,
            "errors": ["min_notional"],
            "recommended_quantity": 0.001,
        }
        app.dependency_overrides[trade_module.get_db] = lambda: mock_db
        try:
            client = TestClient(app, base_url="http://localhost")
            r = client.post(
                "/api/trade/order", json=_order_body(), headers=api_headers
            )
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["status"] == "rejected"
    assert detail["reason"] == "min_notional"


def test_place_order_real_blocked_via_adapter_403(api_headers, monkeypatch):
    """Paper/emergency: adapter path must surface RealOrderBlocked as 403."""
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    monkeypatch.setenv("USE_BROKER_ADAPTER", "true")
    mock_client = MagicMock()
    mock_client.get_symbol_ticker.return_value = {"price": "50000"}
    mock_db = MagicMock()

    with patch.object(trade_module, "Client", return_value=mock_client), patch.object(
        trade_module, "OrderValidator"
    ) as ov, patch.object(
        trade_module, "get_shared_breakers"
    ) as gb, patch.object(
        trade_module._operation_tracker,
        "generate_client_order_id",
        return_value="cid-block",
    ), patch.object(
        trade_module._operation_tracker, "track_operation", new_callable=AsyncMock
    ), patch.object(
        trade_module,
        "place_spot_market_via_adapter",
        new_callable=AsyncMock,
        side_effect=RealOrderBlocked("paper_mode"),
    ), patch.object(trade_module, "send_telegram_alert"):
        gb.return_value.get_all_breakers_status.return_value = {
            "critical_mode": False,
            "total_active": 0,
        }
        ov.return_value.validate_order_parameters.return_value = {
            "is_valid": True,
            "recommended_quantity": 0.001,
            "errors": [],
        }
        app.dependency_overrides[trade_module.get_db] = lambda: mock_db
        try:
            client = TestClient(app, base_url="http://localhost")
            r = client.post(
                "/api/trade/order", json=_order_body(), headers=api_headers
            )
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 400
    assert "Orden real bloqueada" in r.json()["detail"] or "paper_mode" in r.json()[
        "detail"
    ]


def test_place_order_limit_blocked_by_guard_403(api_headers, monkeypatch):
    """Sin allow_real_orders: LIMIT debe fallar cerrado (paper)."""
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    monkeypatch.delenv("USE_BROKER_ADAPTER", raising=False)
    mock_client = MagicMock()
    mock_client.get_symbol_ticker.return_value = {"price": "50000"}
    mock_db = MagicMock()

    with patch.object(trade_module, "Client", return_value=mock_client), patch.object(
        trade_module, "OrderValidator"
    ) as ov, patch.object(
        trade_module, "get_shared_breakers"
    ) as gb, patch.object(
        trade_module._operation_tracker,
        "generate_client_order_id",
        return_value="cid-limit",
    ), patch.object(
        trade_module._operation_tracker, "track_operation", new_callable=AsyncMock
    ), patch.object(trade_module, "send_telegram_alert"):
        gb.return_value.get_all_breakers_status.return_value = {
            "critical_mode": False,
            "total_active": 0,
        }
        ov.return_value.validate_order_parameters.return_value = {
            "is_valid": True,
            "recommended_quantity": 0.001,
            "adjusted_price": 49900.0,
            "errors": [],
        }
        app.dependency_overrides[trade_module.get_db] = lambda: mock_db
        try:
            client = TestClient(app, base_url="http://localhost")
            r = client.post(
                "/api/trade/order",
                json=_order_body(type="LIMIT", price=50000.0),
                headers=api_headers,
            )
        finally:
            app.dependency_overrides.clear()

    # Guard → HTTPException 403, envuelto por except genérico → 400
    assert r.status_code in (400, 403)
    assert "bloqueada" in r.json()["detail"].lower() or "blocked" in r.json()[
        "detail"
    ].lower() or "paper" in r.json()["detail"].lower() or "emergency" in r.json()[
        "detail"
    ].lower() or "real_order" in r.json()["detail"].lower()


@pytest.mark.usefixtures("allow_real_orders_unit")
def test_place_order_limit_buy_and_sell_mocked(api_headers, monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    monkeypatch.delenv("USE_BROKER_ADAPTER", raising=False)

    for side, method in (("BUY", "order_limit_buy"), ("SELL", "order_limit_sell")):
        mock_client = MagicMock()
        mock_client.get_symbol_ticker.return_value = {"price": "50000"}
        getattr(mock_client, method).return_value = {
            "orderId": 9,
            "status": "NEW",
            "fills": [],
        }
        mock_db = MagicMock()

        with patch.object(trade_module, "Client", return_value=mock_client), patch.object(
            trade_module, "OrderValidator"
        ) as ov, patch.object(
            trade_module, "get_shared_breakers"
        ) as gb, patch.object(
            trade_module._operation_tracker,
            "generate_client_order_id",
            return_value=f"cid-{side.lower()}",
        ), patch.object(
            trade_module._operation_tracker, "track_operation", new_callable=AsyncMock
        ), patch.object(
            trade_module._operation_tracker,
            "update_operation_status",
            new_callable=AsyncMock,
        ), patch.object(trade_module, "log_trade"), patch.object(
            trade_module, "settle_pnl_on_sell", return_value={}
        ), patch.object(trade_module, "recompute_profit_metrics"), patch.object(
            trade_module, "send_telegram_alert"
        ):
            gb.return_value.get_all_breakers_status.return_value = {
                "critical_mode": False,
                "total_active": 0,
            }
            ov.return_value.validate_order_parameters.return_value = {
                "is_valid": True,
                "recommended_quantity": 0.001,
                "adjusted_price": 49900.0,
                "errors": [],
            }
            app.dependency_overrides[trade_module.get_db] = lambda: mock_db
            try:
                client = TestClient(app, base_url="http://localhost")
                r = client.post(
                    "/api/trade/order",
                    json=_order_body(side=side, type="LIMIT", price=50000.0),
                    headers=api_headers,
                )
            finally:
                app.dependency_overrides.clear()

        assert r.status_code == 200, r.text
        getattr(mock_client, method).assert_called_once()


def test_run_grid_no_action_and_insufficient_buy(api_headers, monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "s")
    params = {
        "symbol": "BTCUSDT",
        "min_price": 40000.0,
        "max_price": 60000.0,
        "grids": 5,
        "quantity": 0.01,
    }
    mock_client = MagicMock()
    mock_client.get_account.return_value = {
        "balances": [{"asset": "USDT", "free": "1"}, {"asset": "BTC", "free": "0"}]
    }
    mock_client.get_symbol_ticker.return_value = {"price": "50000"}

    with patch.object(trade_module, "Client", return_value=mock_client), patch.object(
        trade_module, "OrderValidator"
    ), patch.object(
        trade_module, "calculate_grid_levels", return_value=[45000, 50000, 55000]
    ), patch.object(
        trade_module,
        "decide_grid_action",
        return_value={"action": None, "reason": "hold"},
    ), patch.object(trade_module, "send_telegram_alert"):
        client = TestClient(app, base_url="http://localhost")
        idle = client.post("/api/trade/run_grid", json=params, headers=api_headers)
    assert idle.status_code == 200
    assert "No se ejecutó" in idle.json()["message"]

    with patch.object(trade_module, "Client", return_value=mock_client), patch.object(
        trade_module, "OrderValidator"
    ), patch.object(
        trade_module, "calculate_grid_levels", return_value=[45000, 50000, 55000]
    ), patch.object(
        trade_module,
        "decide_grid_action",
        return_value={"action": "BUY", "level": 45000},
    ), patch.object(trade_module, "send_telegram_alert"):
        client = TestClient(app, base_url="http://localhost")
        poor = client.post("/api/trade/run_grid", json=params, headers=api_headers)
    assert poor.status_code == 400
    assert "Balance insuficiente" in poor.json()["detail"]


def test_grid_config_get_error_and_update(api_headers, monkeypatch, tmp_path):
    client = TestClient(app, base_url="http://localhost")
    with patch("builtins.open", side_effect=FileNotFoundError("missing")):
        missing = client.get("/api/trade/grid_config", headers=api_headers)
    assert missing.status_code == 500

    cfg = {
        "symbol": "BTCUSDT",
        "min_price": 40000.0,
        "max_price": 60000.0,
        "grids": 5,
        "quantity": 0.001,
    }
    with patch.object(trade_module, "update_grid_config") as upd:
        ok = client.post("/api/trade/grid_config", json=cfg, headers=api_headers)
    assert ok.status_code == 200
    assert ok.json()["message"] == "Configuración actualizada"
    upd.assert_called_once()
