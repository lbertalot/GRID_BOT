import os
import sys
import pytest

# Asegurar que el path del proyecto esté en PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.binance_async import AsyncBinanceWrapper


class DummyClient:
    def __init__(self):
        self.calls = 0

    def get_symbol_ticker(self, symbol: str):
        self.calls += 1
        return {"symbol": symbol, "price": "100.0"}

    def get_klines(self, symbol: str, interval: str, limit: int = 100):
        self.calls += 1
        return [[0, "100", "101", "99", "100", "10", 0]] * limit


@pytest.mark.asyncio
async def test_wrapper_uses_cache(monkeypatch):
    wrapper = AsyncBinanceWrapper(ttl_seconds=2)
    # inyectar dummy sync client
    wrapper.client = DummyClient()

    p1 = await wrapper.get_price("BTCUSDT")
    p2 = await wrapper.get_price("BTCUSDT")

    assert p1 == 100.0 and p2 == 100.0
    # Segunda llamada debe venir de caché (solo 1 llamada real)
    assert wrapper.client.calls == 1
