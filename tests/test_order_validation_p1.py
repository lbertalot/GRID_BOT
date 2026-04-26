"""
Tests P1 (FASE 3) — app/services/order_validation.py
─────────────────────────────────────────────────────────────────
Objetivo: subir cobertura de 68% → ≥90% (TESTING_RULES.md §3).

Cubre:
  - get_symbol_info: cache hit/miss, fallback al cliente directo.
  - _round_to_step / _round_to_tick: precisión Decimal estricta.
  - adjust_quantity_precision: bordes (qty < minQty, qty > maxQty), fallback sin info.
  - validate_order_parameters: MARKET/LIMIT, tickSize, minNotional, rangos de precio.
  - place_market_order_with_validation: éxito + errores Binance (-1111, -2010, -2011).
  - _format_binance_error: ramas por código de error.

Política:
  - Sin tocar la lógica del módulo (TESTING_RULES §1).
  - Mock estricto del cliente Binance.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.order_validation import OrderValidator
# `order_validation.py` importa `BinanceAPIException` desde `binance.exceptions`.
# La firma real (python-binance) requiere un `response` HTTP-like, así que
# subclaseamos para producir excepciones duck-typed con `.code` y `.message`
# que SÍ son del tipo capturado por el `except BinanceAPIException` del módulo.
from app.services.order_validation import BinanceAPIException as _BAE  # type: ignore[attr-defined]


class _FakeBinanceError(_BAE):
    """Hereda del tipo real para ser capturado por except del módulo."""

    def __init__(self, code: int, message: str) -> None:
        # Bypass __init__ del padre (requiere response real).
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.status_code = 400


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────


def _exchange_info(
    symbol: str = "BTCUSDT",
    step: str = "0.0001",
    min_qty: str = "0.0001",
    max_qty: str = "1000.0",
    min_notional: str = "10.0",
    tick: str = "0.01",
    min_price: str = "0.01",
    max_price: str = "1000000.0",
) -> dict:
    return {
        "symbols": [
            {
                "symbol": symbol,
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "quotePrecision": 8,
                "baseAssetPrecision": 8,
                "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": step, "minQty": min_qty, "maxQty": max_qty},
                    {"filterType": "MIN_NOTIONAL", "minNotional": min_notional},
                    {
                        "filterType": "PRICE_FILTER",
                        "tickSize": tick,
                        "minPrice": min_price,
                        "maxPrice": max_price,
                    },
                ],
            }
        ]
    }


@pytest.fixture
def validator() -> tuple[OrderValidator, MagicMock]:
    client = MagicMock()
    client.get_exchange_info.return_value = _exchange_info()
    client.get_symbol_ticker.return_value = {"price": "50000.00"}
    return OrderValidator(client), client


# ─────────────────────────────────────────────────────────────────
# get_symbol_info: cache + fallback
# ─────────────────────────────────────────────────────────────────


def test_get_symbol_info_cachea_resultado(validator):
    v, client = validator
    info1 = v.get_symbol_info("BTCUSDT")
    info2 = v.get_symbol_info("BTCUSDT")
    assert info1 == info2
    assert client.get_exchange_info.call_count == 1


def test_get_symbol_info_extrae_filtros(validator):
    v, _ = validator
    info = v.get_symbol_info("BTCUSDT")
    assert info["stepSize"] == 0.0001
    assert info["minQty"] == 0.0001
    assert info["maxQty"] == 1000.0
    assert info["minNotional"] == 10.0
    assert info["tickSize"] == 0.01


def test_get_symbol_info_simbolo_inexistente(validator):
    v, _ = validator
    info = v.get_symbol_info("DOGEUSDT")
    assert info is None


def test_get_symbol_info_excepcion_devuelve_none():
    client = MagicMock()
    client.get_exchange_info.side_effect = RuntimeError("network down")
    v = OrderValidator(client)
    assert v.get_symbol_info("BTCUSDT") is None


def test_get_symbol_info_cliente_sin_use_cache():
    """Si el cliente NO tiene firma `use_cache`, usa get_exchange_info() pelado."""
    client = MagicMock(spec=["get_exchange_info"])
    client.get_exchange_info.return_value = _exchange_info()
    v = OrderValidator(client)
    info = v.get_symbol_info("BTCUSDT")
    assert info is not None
    assert info["symbol"] == "BTCUSDT"


# ─────────────────────────────────────────────────────────────────
# Rounding helpers
# ─────────────────────────────────────────────────────────────────


def test_round_to_step_basico(validator):
    v, _ = validator
    assert v._round_to_step(0.12345, 0.001) == pytest.approx(0.123)


def test_round_to_step_con_step_cero(validator):
    """step <= 0 debe devolver el valor sin tocar."""
    v, _ = validator
    assert v._round_to_step(0.123, 0) == 0.123


def test_round_to_step_redondea_hacia_abajo(validator):
    """ROUND_DOWN: 0.999 con step 0.5 → 0.5, no 1.0."""
    v, _ = validator
    assert v._round_to_step(0.999, 0.5) == pytest.approx(0.5)


def test_round_to_tick_basico(validator):
    v, _ = validator
    assert v._round_to_tick(50123.456, 0.01) == pytest.approx(50123.45)


def test_round_to_tick_con_tick_cero(validator):
    v, _ = validator
    assert v._round_to_tick(123.456, 0) == 123.456


# ─────────────────────────────────────────────────────────────────
# adjust_quantity_precision
# ─────────────────────────────────────────────────────────────────


def test_adjust_quantity_qty_normal(validator):
    v, _ = validator
    res = v.adjust_quantity_precision(0.00135, "BTCUSDT")
    assert res["adjusted_quantity"] == pytest.approx(0.0013, rel=1e-6)
    assert res["step_size"] == 0.0001


def test_adjust_quantity_menor_que_minimo(validator):
    """Si qty ajustada < minQty, fuerza a minQty."""
    v, _ = validator
    res = v.adjust_quantity_precision(0.00001, "BTCUSDT")
    assert res["adjusted_quantity"] == pytest.approx(0.0001)


def test_adjust_quantity_mayor_que_maximo(validator):
    v, _ = validator
    res = v.adjust_quantity_precision(99999.9, "BTCUSDT")
    assert res["adjusted_quantity"] == pytest.approx(1000.0)


def test_adjust_quantity_simbolo_desconocido_usa_defaults(validator):
    """Cuando get_symbol_info devuelve None, usa fallback."""
    v, _ = validator
    res = v.adjust_quantity_precision(0.5, "DOGEUSDT")
    assert res["step_size"] == 0.001
    assert res["min_qty"] == 0.001
    assert res["min_notional"] == 5.0


# ─────────────────────────────────────────────────────────────────
# validate_order_parameters
# ─────────────────────────────────────────────────────────────────


def test_validate_market_orden_valida(validator):
    v, _ = validator
    res = v.validate_order_parameters("BTCUSDT", 0.001, "BUY", "MARKET")
    assert res["is_valid"] is True
    assert res["errors"] == []
    assert res["notional_value"] == pytest.approx(50.0)


def test_validate_notional_insuficiente_falla(validator):
    """0.0001 BTC * 50000 = 5 USDT < minNotional 10 → error."""
    v, _ = validator
    res = v.validate_order_parameters("BTCUSDT", 0.0001, "BUY", "MARKET")
    assert res["is_valid"] is False
    assert any("notional" in e.lower() for e in res["errors"])


def test_validate_limit_sin_precio_falla(validator):
    v, _ = validator
    res = v.validate_order_parameters("BTCUSDT", 0.001, "BUY", "LIMIT", price=None)
    assert res["is_valid"] is False
    assert any("precio requerido" in e.lower() for e in res["errors"])


def test_validate_limit_redondea_a_tick_y_warning(validator):
    """Precio 50123.456 con tick 0.01 → 50123.45 + warning de ajuste."""
    v, _ = validator
    res = v.validate_order_parameters(
        "BTCUSDT", 0.001, "BUY", "LIMIT", price=50123.456
    )
    assert res["is_valid"] is True
    assert res["adjusted_price"] == pytest.approx(50123.45)
    assert any("tickSize" in w for w in res["warnings"])


def test_validate_limit_precio_fuera_de_rango_max(validator):
    v, _ = validator
    res = v.validate_order_parameters(
        "BTCUSDT", 0.001, "BUY", "LIMIT", price=2_000_000.0
    )
    assert res["is_valid"] is False
    assert any("máximo" in e for e in res["errors"])


def test_validate_warning_si_qty_se_ajusta(validator):
    """Qty 0.00135 → 0.0013 genera warning de ajuste."""
    v, _ = validator
    res = v.validate_order_parameters("BTCUSDT", 0.00135, "BUY", "MARKET")
    assert any("Cantidad ajustada" in w for w in res["warnings"])


def test_validate_excepcion_devuelve_invalid(validator):
    v, client = validator
    client.get_symbol_ticker.side_effect = RuntimeError("api down")
    res = v.validate_order_parameters("BTCUSDT", 0.001, "BUY", "MARKET")
    assert res["is_valid"] is False
    assert any("Error en validación" in e for e in res["errors"])


# ─────────────────────────────────────────────────────────────────
# place_market_order_with_validation
# ─────────────────────────────────────────────────────────────────


def test_place_market_order_buy_exitoso(validator):
    v, client = validator
    client.order_market_buy.return_value = {"orderId": 1, "status": "FILLED"}
    res = v.place_market_order_with_validation("BTCUSDT", "BUY", 0.001)
    assert res["order"]["orderId"] == 1
    assert res["executed_quantity"] == pytest.approx(0.001)
    client.order_market_buy.assert_called_once()


def test_place_market_order_sell_exitoso(validator):
    v, client = validator
    client.order_market_sell.return_value = {"orderId": 2, "status": "FILLED"}
    res = v.place_market_order_with_validation("BTCUSDT", "SELL", 0.001)
    assert res["order"]["orderId"] == 2
    client.order_market_sell.assert_called_once()


def test_place_market_order_lado_invalido(validator):
    v, _ = validator
    with pytest.raises(ValueError, match="Lado de orden inválido"):
        v.place_market_order_with_validation("BTCUSDT", "HOLD", 0.001)


def test_place_market_order_validacion_falla_no_envia_orden(validator):
    """Si la validación falla, NO se debe llamar a Binance."""
    v, client = validator
    with pytest.raises(ValueError, match="Parámetros de orden inválidos"):
        v.place_market_order_with_validation("BTCUSDT", "BUY", 0.0001)
    client.order_market_buy.assert_not_called()


def test_place_market_order_binance_error_se_formatea(validator):
    v, client = validator
    err = _FakeBinanceError(code=-1111, message="LOT_SIZE precision")
    client.order_market_buy.side_effect = err
    with pytest.raises(ValueError, match="Precisión"):
        v.place_market_order_with_validation("BTCUSDT", "BUY", 0.001)


# ─────────────────────────────────────────────────────────────────
# _format_binance_error: ramas por código
# ─────────────────────────────────────────────────────────────────


def test_format_binance_error_1111_con_symbol_info(validator):
    v, _ = validator
    err = _FakeBinanceError(code=-1111, message="LOT_SIZE")
    msg = v._format_binance_error(err, "BTCUSDT", "BUY", 0.001)
    assert "Precisión" in msg
    assert "Step Size" in msg


def test_format_binance_error_1111_sin_symbol_info():
    """Si get_symbol_info falla, debe usar el path alternativo."""
    client = MagicMock()
    client.get_exchange_info.side_effect = RuntimeError("down")
    v = OrderValidator(client)
    err = _FakeBinanceError(code=-1111, message="LOT_SIZE")
    msg = v._format_binance_error(err, "BTCUSDT", "BUY", 0.001)
    assert "Precisión" in msg
    assert "Sugerencia" in msg


def test_format_binance_error_2010_balance(validator):
    v, _ = validator
    err = _FakeBinanceError(code=-2010, message="insufficient")
    msg = v._format_binance_error(err, "BTCUSDT", "BUY", 0.001)
    assert "Balance Insuficiente" in msg


def test_format_binance_error_2011_precio(validator):
    v, _ = validator
    err = _FakeBinanceError(code=-2011, message="bad price")
    msg = v._format_binance_error(err, "BTCUSDT", "BUY", 0.001)
    assert "Error de Precio" in msg


def test_format_binance_error_generico(validator):
    v, _ = validator
    err = _FakeBinanceError(code=-9999, message="other")
    msg = v._format_binance_error(err, "BTCUSDT", "BUY", 0.001)
    assert "Error de Binance API" in msg
