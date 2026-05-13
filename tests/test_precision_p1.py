import pytest
from decimal import Decimal
from app.core.precision_validator import PrecisionValidator

def test_precision_loss_with_floats():
    """
    Test para demostrar la precisión con Decimal.
    Usamos un notional > $10 para pasar la validación mínima de Binance.
    """
    validator = PrecisionValidator()
    
    symbol = "BTCUSDT"
    quantity = 0.0002 # 0.0002 * 60000 = $12
    price = 60000.0
    
    is_valid, data, msg = validator.validate_order(symbol, quantity, price)
    
    assert is_valid is True, f"Fallo: {msg}"
    assert isinstance(data["quantity"], Decimal)
    assert data["notional_value"] >= Decimal("10.0")

def test_min_notional_precision_boundary():
    """
    Test de borde para MIN_NOTIONAL.
    $9.99999999 debe ser RECHAZADO.
    $10.00000000 debe ser ACEPTADO.
    """
    validator = PrecisionValidator()
    symbol = "BTCUSDT"
    
    # Caso 1: Justo por debajo de $10
    price = 100.0
    quantity = 0.09999 
    
    is_valid, data, msg = validator.validate_order(symbol, quantity, price)
    assert is_valid is False
    assert "notional muy bajo" in msg.lower()

    # Caso 2: Justo en $10
    quantity = 0.1
    is_valid, data, msg = validator.validate_order(symbol, quantity, price)
    assert is_valid is True
    assert data["notional_value"] == Decimal("10.0")

@pytest.mark.parametrize("symbol, quantity, price", [
    ("BTCUSDT", 0.000515, 50000.0), # 0.000515 * 50000 = 25.75 -> Ajusta a 0.00051
    ("ETHUSDT", 0.01015, 3000.0),   # 0.01015 * 3000 = 30.45 -> Ajusta a 0.0101
])
def test_step_size_adjustment_precision(symbol, quantity, price):
    validator = PrecisionValidator()
    is_valid, data, msg = validator.validate_order(symbol, quantity, price)
    
    assert is_valid is True, f"Fallo para {symbol}: {msg}"
    assert isinstance(data["quantity"], Decimal)
    
    # Verificamos que el ajuste sea hacia ABAJO al step_size más cercano
    if symbol == "BTCUSDT":
        # step_size = 0.00001
        assert data["quantity"] == Decimal("0.00051")
    elif symbol == "ETHUSDT":
        # step_size = 0.0001
        assert data["quantity"] == Decimal("0.0101")
