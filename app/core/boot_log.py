"""Banners de arranque: un INFO por proceso, el resto DEBUG.

Paper-only. No altera órdenes ni freeze L0.
"""

from __future__ import annotations

from typing import Any, Set

_seen: Set[str] = set()


def boot_info(logger: Any, key: str, message: str) -> None:
    """Emite INFO la primera vez; DEBUG si el módulo se re-instancia en el ciclo."""
    if key in _seen:
        logger.debug(message)
        return
    _seen.add(key)
    logger.info(message)


def reset_boot_log_for_tests() -> None:
    _seen.clear()
