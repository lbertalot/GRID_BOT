"""
Precision & Normalization utilities for Binance symbols.

Provides a small cache over exchange_info and pure functions to:
- round_price(symbol, price)
- round_quantity(symbol, quantity)
- validate_notional(symbol, price, quantity)

All functions are side-effect free except cache warm/load.
"""

from __future__ import annotations

from typing import Dict, Optional, Any
import time
import threading

from binance.client import Client


class PrecisionNormalizer:
    """Caches exchange_info filters and exposes precision helpers."""

    def __init__(self, client: Client, ttl_seconds: int = 900) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_load: float = 0.0

    def _ensure_loaded(self, symbols: Optional[list[str]] = None) -> None:
        now = time.time()
        if (now - self._last_load) < self._ttl_seconds and self._cache:
            return
        with self._lock:
            if (time.time() - self._last_load) < self._ttl_seconds and self._cache:
                return
            info = self._client.get_exchange_info()
            new_map: Dict[str, Dict[str, Any]] = {}
            for s in info.get("symbols", []):
                sym = s.get("symbol")
                if not sym:
                    continue
                if symbols and sym not in symbols:
                    continue
                filters = {f["filterType"]: f for f in s.get("filters", [])}
                new_map[sym] = {
                    "tickSize": float(filters.get("PRICE_FILTER", {}).get("tickSize", 0.0) or 0.0),
                    "minPrice": float(filters.get("PRICE_FILTER", {}).get("minPrice", 0.0) or 0.0),
                    "maxPrice": float(filters.get("PRICE_FILTER", {}).get("maxPrice", 0.0) or 0.0),
                    "stepSize": float(filters.get("LOT_SIZE", {}).get("stepSize", 0.0) or 0.0),
                    "minQty": float(filters.get("LOT_SIZE", {}).get("minQty", 0.0) or 0.0),
                    "maxQty": float(filters.get("LOT_SIZE", {}).get("maxQty", 0.0) or 0.0),
                    "minNotional": float(filters.get("MIN_NOTIONAL", {}).get("minNotional", 0.0) or 0.0),
                }
            self._cache = new_map
            self._last_load = time.time()

    def round_price(self, symbol: str, price: float) -> float:
        self._ensure_loaded()
        data = self._cache.get(symbol.upper())
        if not data:
            return price
        tick = data.get("tickSize", 0.0)
        if tick <= 0:
            return price
        # Snap to grid: floor(price / tick) * tick
        steps = int(price / tick)
        return round(steps * tick, 8)

    def round_quantity(self, symbol: str, quantity: float) -> float:
        self._ensure_loaded()
        data = self._cache.get(symbol.upper())
        if not data:
            return quantity
        step = data.get("stepSize", 0.0)
        if step <= 0:
            return quantity
        steps = int(quantity / step)
        return round(steps * step, 8)

    def validate_notional(self, symbol: str, price: float, quantity: float) -> bool:
        self._ensure_loaded()
        data = self._cache.get(symbol.upper())
        if not data:
            return True
        min_notional = data.get("minNotional", 0.0)
        return (price * quantity) >= min_notional


__all__ = [
    "PrecisionNormalizer",
]


