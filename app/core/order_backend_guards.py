"""Fail-closed previo a colocar orden: ticker y Postgres. No muta breakers."""

from __future__ import annotations

from typing import Optional


def fail_closed_order_block(
    *,
    ticker_available: bool,
    postgres_available: bool,
) -> Optional[str]:
    if not ticker_available:
        return "fail_closed: ticker unavailable"
    if not postgres_available:
        return "fail_closed: postgres unavailable"
    return None
