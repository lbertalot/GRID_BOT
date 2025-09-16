import os
import sys
import time
import types
import requests
import pytest

# Asegurar que /app esté en PYTHONPATH antes de importar 'app'
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.optimized_grid_manager import GridManagerConfig, AssetConfig


# Install a lightweight stub of the Binance SDK for all tests unless explicitly disabled
if os.getenv("USE_REAL_BINANCE") != "1":
    fake_binance = types.ModuleType("binance")

    class BinanceAPIException(Exception):
        def __init__(self, status_code: int = 400, message: str = "Error", code: int | None = None):
            super().__init__(message)
            self.status_code = status_code
            self.message = message
            self.code = code if code is not None else -1000

    def _fake_balances():
        return [
            {"asset": "USDT", "free": "1000.00", "locked": "0.00"},
            {"asset": "BTC", "free": "0.01", "locked": "0.00"},
        ]

    def _fake_symbol_info(symbol: str):
        return {
            "symbol": symbol,
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "filters": [
                {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "1000000", "tickSize": "0.01"},
                {"filterType": "LOT_SIZE", "minQty": "0.0001", "maxQty": "1000", "stepSize": "0.0001"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
            ],
        }

    def _fake_exchange_info():
        symbols = [
            {"symbol": s, "status": "TRADING", "filters": _fake_symbol_info(s)["filters"]}
            for s in ["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "SOLUSDT"]
        ]
        return {"timezone": "UTC", "serverTime": int(time.time() * 1000), "symbols": symbols}

    class _Client:
        def __init__(self, api_key: str | None = None, api_secret: str | None = None, *_, **__):
            self.api_key = api_key
            self.api_secret = api_secret

        # Account and permissions
        def get_account(self):
            return {
                "accountType": "SPOT",
                "makerCommission": 10,
                "takerCommission": 10,
                "balances": _fake_balances(),
            }

        def get_open_orders(self, *_, **__):
            return []

        # Public market data
        def get_symbol_ticker(self, symbol: str):
            base_price = {
                "BTCUSDT": 50000.0,
                "ETHUSDT": 3500.0,
                "ADAUSDT": 0.5,
                "BNBUSDT": 600.0,
                "SOLUSDT": 150.0,
            }.get(symbol, 100.0)
            return {"symbol": symbol, "price": str(base_price)}

        def get_symbol_info(self, symbol: str):
            return _fake_symbol_info(symbol)

        def get_exchange_info(self):
            return _fake_exchange_info()

        def get_ticker(self, symbol: str):
            price = float(self.get_symbol_ticker(symbol)["price"])
            return {
                "lastPrice": str(price),
                "priceChangePercent": "1.23",
                "volume": "12345.678",
                "highPrice": str(price * 1.02),
                "lowPrice": str(price * 0.98),
            }

        def get_recent_trades(self, symbol: str, limit: int = 5):
            now = int(time.time() * 1000)
            return [
                {"price": str(100 + i), "qty": str(0.001 + i * 0.0001), "isBuyerMaker": bool(i % 2), "time": now - i * 60000}
                for i in range(limit)
            ]

        def get_klines(self, symbol: str, interval: str, limit: int = 10):
            now = int(time.time() * 1000)
            result = []
            for i in range(limit):
                open_time = now - (limit - i) * 60_000
                close_time = open_time + 60_000
                open_price = 100.0 + i
                high_price = open_price * 1.01
                low_price = open_price * 0.99
                close_price = open_price * 1.005
                volume = 10 + i
                result.append([
                    open_time,
                    str(open_price),
                    str(high_price),
                    str(low_price),
                    str(close_price),
                    str(volume),
                    close_time,
                ])
            return result

        # Trading (simulated)
        def order_market_buy(self, symbol: str, quantity: float, *_, **__):
            price = float(self.get_symbol_ticker(symbol)["price"])
            return {
                "symbol": symbol,
                "orderId": 12345,
                "status": "FILLED",
                "fills": [{"price": str(price), "qty": str(quantity)}],
            }

        def order_market_sell(self, symbol: str, quantity: float, *_, **__):
            price = float(self.get_symbol_ticker(symbol)["price"])
            return {
                "symbol": symbol,
                "orderId": 12346,
                "status": "FILLED",
                "fills": [{"price": str(price), "qty": str(quantity)}],
            }

        # Misc
        def get_server_time(self):
            return {"serverTime": int(time.time() * 1000)}

    class _AsyncClient:
        @classmethod
        async def create(cls, api_key: str | None = None, api_secret: str | None = None, *_, **__):
            return cls(api_key, api_secret)

        def __init__(self, api_key: str | None = None, api_secret: str | None = None):
            self.api_key = api_key
            self.api_secret = api_secret

        async def get_symbol_ticker(self, symbol: str):
            return {"symbol": symbol, "price": "50000.0"}

        async def close_connection(self):
            return None

    # Expose in module and submodules to satisfy various import styles
    fake_binance.Client = _Client
    fake_binance.AsyncClient = _AsyncClient

    exceptions_mod = types.ModuleType("binance.exceptions")
    exceptions_mod.BinanceAPIException = BinanceAPIException
    client_mod = types.ModuleType("binance.client")
    client_mod.Client = _Client

    sys.modules["binance"] = fake_binance
    sys.modules["binance.client"] = client_mod
    sys.modules["binance.exceptions"] = exceptions_mod

@pytest.fixture
def mock_config():
    # Configuración mínima para OptimizedGridManager en tests
    assets = {
        "BTCUSDT": AssetConfig(symbol="BTCUSDT", min_price=10000.0, max_price=200000.0, grids=10, quantity=0.0001),
        "ETHUSDT": AssetConfig(symbol="ETHUSDT", min_price=500.0, max_price=10000.0, grids=10, quantity=0.01),
    }
    return GridManagerConfig(assets=assets, update_interval=60, min_notional_threshold=10.0)


@pytest.fixture(scope="session", autouse=True)
def wait_api_ready():
    if os.getenv("SKIP_API_HEALTHCHECK") == "1":
        return
    base_url = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")
    deadline = time.time() + 45
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/health", timeout=5)
            if r.status_code == 200:
                return
        except Exception as e:
            last_err = e
        time.sleep(2)
    raise RuntimeError(f"API no disponible en {base_url} tras espera: {last_err}")


# Cliente de pruebas FastAPI para tests que usan 'client'
try:
    from fastapi.testclient import TestClient
    from app.main import app

    @pytest.fixture
    def client():
        return TestClient(app)
except Exception:
    # Si falla, los tests que requieran 'client' se saltarán/fracasar.
    pass
