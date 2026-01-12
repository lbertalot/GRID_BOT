"""
⚠️ DEPRECATED: Este módulo está deprecado. Usa binance_client_singleton en su lugar.

Este módulo se mantiene solo para compatibilidad hacia atrás.
Todos los usos deberían migrarse a:
    from app.services.binance_client_singleton import get_binance_client_singleton
    client = get_binance_client_singleton().client

Este módulo será eliminado en una versión futura.
"""

import os
import warnings
from dotenv import load_dotenv

# ⚠️ Warning de deprecación
warnings.warn(
    "app.services.binance_client está deprecado. "
    "Usa app.services.binance_client_singleton en su lugar. "
    "Este módulo será eliminado en una versión futura.",
    DeprecationWarning,
    stacklevel=2
)

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
    # ✅ FASE 4: Usar singleton en lugar de crear nuevo cliente
    try:
        from app.services.binance_client_singleton import get_binance_client_singleton
        singleton = get_binance_client_singleton()
        if singleton.is_ready():
            client = singleton.client
        else:
            # Fallback si singleton no está listo
            from binance.client import Client
            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_SECRET_KEY")
            testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
            client = Client(api_key, api_secret, testnet=testnet)
    except Exception:
        # Fallback a dummy en caso de error
        from binance.client import Client
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_SECRET_KEY")
        testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
        try:
            client = Client(api_key, api_secret, testnet=testnet)
        except Exception:
            class _FallbackDummy:
                def get_account(self, *_: object, **__: object):
                    return {"balances": []}
                def get_symbol_ticker(self, symbol: str):
                    return {"symbol": symbol, "price": "0"}
            client = _FallbackDummy()
