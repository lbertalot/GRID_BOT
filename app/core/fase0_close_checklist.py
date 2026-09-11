"""Veredicto read-only de cierre Fase 0 (14-sep). No firma. Paper-only."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict


def fase0_close_verdict(
    *,
    a2_fail: bool,
    pnl_net: Decimal,
    closed_cycles: int,
    min_cycles: int = 120,
) -> Dict[str, Any]:
    """ITERATE si A2 rojo, PnL neto < 0 o ciclos insuficientes. Nunca PROMOTE_PAPER."""
    reasons = []
    if a2_fail:
        reasons.append("A2_rojo")
    if pnl_net < Decimal("0"):
        reasons.append("pnl_neto_negativo")
    if int(closed_cycles) < int(min_cycles):
        reasons.append("ciclos_insuficientes")
    iterate = bool(reasons)
    return {
        "verdict": "ITERATE" if iterate else "REVIEW",
        "promote_paper": False,
        "promote_live": False,
        "firma_humana_pendiente": True,
        "reasons": reasons,
        "human_signature": None,
    }
