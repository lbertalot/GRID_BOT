import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_backtest_trailing_stop():
    client = TestClient(app)
    response = client.post(
        "/strategy/backtest?strategy=trailing_stop",
        json={
            "symbol": "BTCUSDT",
            "interval": "1h",
            "limit": 15,
            "balances": {"BTC": 0.01, "USDT": 100},
            "params": {"trailing_pct": 0.01}
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert "action" in data[-1] 