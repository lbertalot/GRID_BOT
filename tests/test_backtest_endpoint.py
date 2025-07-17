import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_backtest_trailing_stop():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
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