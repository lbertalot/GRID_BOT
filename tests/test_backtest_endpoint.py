import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_backtest_trailing_stop():
    client = TestClient(app)
    # Histórico sintético: evita llamar a Binance en CI (sin API keys reales)
    synthetic = [100.0 + i * 0.05 for i in range(15)]
    response = client.post(
        "/strategy/backtest?strategy=trailing_stop",
        json={
            "symbol": "BTCUSDT",
            "interval": "1h",
            "limit": 15,
            "balances": {"BTC": 0.01, "USDT": 100},
            "params": {"trailing_pct": 0.01},
            "price_history": synthetic,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert "action" in data[-1]


def test_backtest_rejects_short_price_history():
    client = TestClient(app)
    response = client.post(
        "/strategy/backtest?strategy=trailing_stop",
        json={
            "symbol": "BTCUSDT",
            "interval": "1h",
            "limit": 15,
            "balances": {"BTC": 0.01, "USDT": 100},
            "params": {"trailing_pct": 0.01},
            "price_history": [1.0, 2.0, 3.0],
        },
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "strategy_name",
    ["trailing_stop", "scalping", "rsi_macd"],
)
def test_backtest_offline_each_strategy(strategy_name: str):
    """Ejecuta backtest sin Binance para subir cobertura del router y estrategias."""
    client = TestClient(app)
    history = [100.0 + 0.3 * i + (0.1 if i % 4 == 0 else 0) for i in range(40)]
    response = client.post(
        f"/strategy/backtest?strategy={strategy_name}",
        json={
            "symbol": "BTCUSDT",
            "interval": "1h",
            "limit": 40,
            "balances": {"BTC": 0.01, "USDT": 100},
            "params": {"trailing_pct": 0.02},
            "price_history": history,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "action" in data[-1]
