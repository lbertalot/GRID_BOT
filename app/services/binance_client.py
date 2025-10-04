import os
from dotenv import load_dotenv

load_dotenv()

USE_REAL = os.getenv("USE_REAL_BINANCE", "0") == "1"

if not USE_REAL:
    class _DummyClient:
        def __init__(self, *_: object, **__: object) -> None:
            pass
        def get_account(self, *_: object, **__: object):
            return {"balances": []}
        def get_symbol_ticker(self, symbol: str):
            return {"symbol": symbol, "price": "0"}
        def order_market_buy(self, *args, **kwargs):
            return {"orderId": 1, "status": "FILLED", "fills": []}
        def order_market_sell(self, *args, **kwargs):
            return {"orderId": 2, "status": "FILLED", "fills": []}
    client = _DummyClient()
else:
    from binance.client import Client
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    # Instanciar sin side-effects adicionales; si la lib pingea, se recomienda usar testnet
    testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
    try:
        client = Client(api_key, api_secret, testnet=testnet)
    except Exception:
        # Fallback a dummy en caso de error de red durante import
        class _FallbackDummy:
            def get_account(self, *_: object, **__: object):
                return {"balances": []}
            def get_symbol_ticker(self, symbol: str):
                return {"symbol": symbol, "price": "0"}
        client = _FallbackDummy()
