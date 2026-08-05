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
        # LDUSDT + quote sintético: no inventar USDTBUSD / USDTBTC (ruido Earn)
        ("LDUSDTBUSD", None),
        ("LDUSDTBTC", None),
        ("LDETHUSDT", "ETHUSDT"),
        ("LDBNBUSDT", "BNBUSDT"),
        ("LDBTCUSDT", "BTCUSDT"),
        ("BTCUSDT", None),
        ("LDFOO", None),
    ],
)
def test_fallback_ld_prefixed_spot_symbol_maps_or_returns_none(
    symbol: str, expected: str | None
) -> None:
    assert fallback_ld_prefixed_spot_symbol(symbol) == expected


@pytest.mark.parametrize(
    ("asset", "expected"),
    [
        ("LDUSDT", "USDT"),
        ("LDETH", "ETH"),
        ("ldbtc", "BTC"),
        ("USDT", None),
        ("ETH", None),
        ("", None),
    ],
)
def test_binance_earn_underlying_asset(asset: str, expected: str | None) -> None:
    from app.services.binance_client_singleton import binance_earn_underlying_asset

    assert binance_earn_underlying_asset(asset) == expected
