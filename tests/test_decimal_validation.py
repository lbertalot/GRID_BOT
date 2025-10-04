from app.services.order_validation import OrderValidator


class _DummyClient:
    def get_exchange_info(self):
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "quotePrecision": 8,
                    "baseAssetPrecision": 8,
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.10", "minPrice": "0.0", "maxPrice": "1000000"},
                        {"filterType": "LOT_SIZE", "minQty": "0.0001", "maxQty": "1000", "stepSize": "0.0001"},
                        {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                    ],
                }
            ]
        }

    def get_symbol_ticker(self, symbol: str):
        assert symbol == "BTCUSDT"
        return {"symbol": symbol, "price": "50000.0"}


def test_decimal_notional_and_rounding():
    ov = OrderValidator(_DummyClient())
    v = ov.validate_order_parameters("BTCUSDT", quantity=0.00010999, side="BUY", order_type="LIMIT", price=50000.123)
    assert v["is_valid"] is True
    # Cantidad debe ajustarse a stepSize 0.0001
    assert abs(v["quantity_info"]["adjusted_quantity"] - 0.0001) < 1e-12
    # Precio debe ajustarse a tick 0.10
    assert abs(v["adjusted_price"] - 50000.1) < 1e-9
    # Notional usa precisión decimal
    assert v["notional_value"] >= 10.0


