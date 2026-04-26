import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.order_validation import OrderValidator


class DummyClient:
    def __init__(self):
        self.exchange_info = {
            "symbols": [
                {
                    "symbol": "TESTUSDT",
                    "baseAsset": "TEST",
                    "quoteAsset": "USDT",
                    "quotePrecision": 2,
                    "baseAssetPrecision": 6,
                    "filters": [
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.010000",
                            "maxQty": "1000.000000",
                            "stepSize": "0.010000",
                        },
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "0.010000",
                            "maxPrice": "100000.000000",
                            "tickSize": "0.010000",
                        },
                        {"filterType": "MIN_NOTIONAL", "minNotional": "10.000000"},
                    ],
                }
            ]
        }

    def get_exchange_info(self):
        return self.exchange_info

    def get_symbol_ticker(self, symbol: str):
        return {"symbol": symbol, "price": "100.00"}


def test_quantity_adjustment_and_limits():
    v = OrderValidator(DummyClient())
    info = v.adjust_quantity_precision(0.009, "TESTUSDT")
    assert info["adjusted_quantity"] >= info["min_qty"]
    assert info["adjusted_quantity"] == info["min_qty"]


def test_min_notional_validation_market():
    v = OrderValidator(DummyClient())
    # 0.05 * 100 = 5 < minNotional(10)
    result = v.validate_order_parameters("TESTUSDT", 0.05, "BUY", "MARKET")
    assert result["is_valid"] is False
    assert any("notional" in e.lower() for e in result["errors"])


def test_limit_order_price_adjustment_and_range():
    v = OrderValidator(DummyClient())
    # Precio no múltiplo de tick; se ajusta hacia abajo
    result = v.validate_order_parameters("TESTUSDT", 0.2, "BUY", "LIMIT", price=100.007)
    assert result["is_valid"] is True
    assert result["adjusted_price"] == 100.00
    # Precio por debajo del mínimo
    bad = v.validate_order_parameters("TESTUSDT", 0.2, "BUY", "LIMIT", price=0.001)
    assert bad["is_valid"] is False
    assert any("mínimo" in e.lower() for e in bad["errors"])
