import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)

# --- ENDPOINT: /order ---
def test_order_market_buy_success():
    with patch("app.api.trade.Client") as mock_client, \
         patch("app.api.trade.log_trade") as mock_log_trade:
        mock_instance = mock_client.return_value
        mock_instance.order_market_buy.return_value = {"fills": [{"price": "100.0"}]}
        response = client.post("/order", json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.01,
            "type": "MARKET"
        })
        assert response.status_code == 200
        assert "order" in response.json()
        mock_log_trade.assert_called_once()

def test_order_invalid_side():
    response = client.post("/order", json={
        "symbol": "BTCUSDT",
        "side": "INVALID",
        "quantity": 0.01,
        "type": "MARKET"
    })
    assert response.status_code == 400
    assert "Lado de orden inválido" in response.text

# --- ENDPOINT: /run_grid ---
def test_run_grid_success():
    with patch("app.api.trade.Client") as mock_client, \
         patch("app.services.grid_strategy.calculate_grid_levels", return_value=[100, 200, 300]), \
         patch("app.services.grid_strategy.decide_grid_action", return_value={"action": "BUY"}):
        mock_instance = mock_client.return_value
        mock_instance.get_symbol_ticker.return_value = {"price": "150"}
        mock_instance.order_market_buy.return_value = {"orderId": 1}
        response = client.post("/run_grid", json={
            "symbol": "BTCUSDT",
            "min_price": 100,
            "max_price": 300,
            "grids": 3,
            "quantity": 0.01,
            "last_action": None
        })
        assert response.status_code == 200
        assert "decision" in response.json()

# --- ENDPOINT: /strategy/scalping ---
def test_strategy_scalping_success():
    with patch("app.api.strategies.get_price_history", return_value=[100, 99, 98]):
        response = client.post("/strategy/scalping", json={
            "symbol": "BTCUSDT",
            "interval": "1m",
            "limit": 3,
            "balances": {"USDT": 100},
            "params": {}
        })
        assert response.status_code == 200
        assert response.json()["action"] in ["BUY", "SELL", "HOLD"]

# --- ENDPOINT: /strategy/backtest ---
def test_strategy_backtest_success():
    with patch("app.api.strategies.get_price_history", return_value=[100 + i for i in range(20)]):
        response = client.post("/strategy/backtest?strategy=scalping", json={
            "symbol": "BTCUSDT",
            "interval": "1h",
            "limit": 20,
            "balances": {"USDT": 100},
            "params": {}
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert "action" in response.json()[-1]

# --- Casos de error ---
def test_strategy_backtest_invalid_strategy():
    response = client.post("/strategy/backtest?strategy=invalid", json={
        "symbol": "BTCUSDT",
        "interval": "1h",
        "limit": 20,
        "balances": {"USDT": 100},
        "params": {}
    })
    assert response.status_code == 422 or response.status_code == 400 