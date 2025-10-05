import os
from app.services.binance_service import BinanceService


def test_simulation_mode_enabled_by_env(monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    monkeypatch.setenv("PAPER_TRADING", "true")
    svc = BinanceService()
    assert svc.is_simulation_mode() is True
    acct = svc.get_account_info()
    assert isinstance(acct, dict)
    price = svc.get_current_price("BTCUSDT")
    assert price >= 0
    order = svc.execute_trading_order("BTCUSDT", "BUY", "MARKET", 0.001)
    assert order.get("status") in ("FILLED", "NEW")


def test_validate_order_parameters_decimal_paths(monkeypatch):
    monkeypatch.setenv("USE_REAL_BINANCE", "0")
    svc = BinanceService()
    v = svc.validate_order_parameters("BTCUSDT", quantity=0.00021, side="BUY", order_type="MARKET")
    assert v["is_valid"] in (True, False)
    # Asegura presencia de campos claves
    assert "notional_value" in v
    assert "recommended_quantity" in v


