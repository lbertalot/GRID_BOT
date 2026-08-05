"""Fallback de símbolos LD* para precios spot (binance_client_singleton)."""

from __future__ import annotations

import pytest

from app.services.binance_client_singleton import fallback_ld_prefixed_spot_symbol


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("LDUSDTUSDT", None),
        ("ldusdtusdt", None),
        ("LD-USDT-USDT", None),
        ("LDUSDTBUSD", "USDTBUSD"),
        ("LDETHUSDT", "ETHUSDT"),
        ("LDBNBUSDT", "BNBUSDT"),
        ("LDUSDTBTC", "USDTBTC"),
        ("BTCUSDT", None),
        ("LDFOO", None),
    ],
)
def test_fallback_ld_prefixed_spot_symbol_maps_or_returns_none(
    symbol: str, expected: str | None
) -> None:
    assert fallback_ld_prefixed_spot_symbol(symbol) == expected
