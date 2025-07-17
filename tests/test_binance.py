import pytest
from binance import AsyncClient
import os

@pytest.mark.asyncio
async def test_binance_connection():
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = await AsyncClient.create(api_key, api_secret)
    ticker = await client.get_symbol_ticker(symbol="BTCUSDT")
    await client.close_connection()
    assert "price" in ticker
    assert float(ticker["price"]) > 0 