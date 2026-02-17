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
    """Verifica redondeo correcto y rechazo por notional insuficiente.
    
    qty=0.00010999 con stepSize=0.0001 -> adjusted=0.0001
    price=50000.123 con tickSize=0.10 -> adjusted=50000.1
    notional=0.0001 * 50000.1 = 5.0001 < minNotional(10) -> RECHAZADO
    
    INV-002: minNotional se valida DESPUÉS del redondeo.
    """
    from decimal import Decimal
    ov = OrderValidator(_DummyClient())
    v = ov.validate_order_parameters("BTCUSDT", quantity=0.00010999, side="BUY", order_type="LIMIT", price=50000.123)
    # Con Decimal correcto, 0.0001 * 50000.1 = 5.0001 < 10 -> rechazado
    assert v["is_valid"] is False, "Notional 5.0001 < minNotional 10 debe ser rechazado"
    assert any("notional" in e.lower() for e in v["errors"])
    # Verificar que el redondeo es correcto
    assert v["quantity_info"]["adjusted_quantity"] == Decimal("0.0001")
    assert v["adjusted_price"] == Decimal("50000.1")


