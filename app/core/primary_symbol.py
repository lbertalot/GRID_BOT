"""Símbolo primario del bot (paper L0 freeze = ETHUSDT).

Usado por portfolio_snapshots y telemetría paper para no etiquetar BTCUSDT
cuando la ventana L0 opera solo ETHUSDT.
"""

from __future__ import annotations

import os


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def resolve_primary_symbol() -> str:
    """Resuelve el símbolo de referencia para snapshots / labels.

    Precedencia:
    1. ``TRADING_SYMBOL`` o ``PRIMARY_SYMBOL`` (explícito)
    2. Paper (sin FORCE_REAL_MODE): ``PAPER_L0_SYMBOL`` o **ETHUSDT** (freeze L0)
    3. Fallback histórico: BTCUSDT
    """
    explicit = (os.getenv("TRADING_SYMBOL") or os.getenv("PRIMARY_SYMBOL") or "").strip()
    if explicit:
        return explicit.upper()

    paper = _env_bool("PAPER_TRADING", "true")
    force_real = _env_bool("FORCE_REAL_MODE", "false")
    if paper and not force_real:
        l0 = (os.getenv("PAPER_L0_SYMBOL") or "ETHUSDT").strip()
        return (l0 or "ETHUSDT").upper()

    return "BTCUSDT"


__all__ = ["resolve_primary_symbol"]
