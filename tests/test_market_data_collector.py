import os
import sys
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.market_data_collector import MarketDataCollector


@pytest.mark.asyncio
async def test_get_price_and_klines_cached(monkeypatch):
    c = MarketDataCollector(ttl_seconds=1)
    price1 = await c.get_price("BTCUSDT")
    price2 = await c.get_price("BTCUSDT")
    assert isinstance(price1, float)
    assert price1 == price2  # cache TTL corto
    kl1 = await c.get_klines("BTCUSDT", "1m", 2)
    kl2 = await c.get_klines("BTCUSDT", "1m", 2)
    assert isinstance(kl1, list) and len(kl1) == len(kl2)


@pytest.mark.asyncio
async def test_validate_order_parameters():
    c = MarketDataCollector(ttl_seconds=1)
    res = await c.validate_order("BTCUSDT", 0.001, order_type="MARKET")
    assert isinstance(res, dict)
    assert "recommended_quantity" in res
