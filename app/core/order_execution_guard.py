"""Guard de ejecución de órdenes reales (S-GATE / B15 + B26).

Ningún ``create_order`` autenticado hacia el exchange puede ejecutarse salvo que
``effective_mode == real_armed`` (flags de entorno + live gate dual firmado).

Paper y price feeds públicos no pasan por aquí. Este módulo solo bloquea el
path de **órdenes reales**.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RealOrderBlocked(RuntimeError):
    """Orden real rechazada por modo, kill-switch o live gate."""

    def __init__(self, reason: str, *, snapshot: Optional[Dict[str, Any]] = None):
        self.reason = reason
        self.snapshot = snapshot or {}
        super().__init__(f"real_order_blocked: {reason}")


def assert_real_order_allowed(*, context: str = "") -> Dict[str, Any]:
    """Fail-closed: solo ``real_armed`` puede crear órdenes en el exchange.

    Cubre:
    - B15: el live gate debe estar firmado (vía ``effective_mode``).
    - B26: ``EMERGENCY_STOP`` / ``TRADING_ENABLED=false`` bloquean (vía modo).
    - Paper: ``PAPER_TRADING`` sin ``FORCE_REAL_MODE`` → ``paper`` → bloqueo.
    """
    from app.core.trading_mode import get_trading_mode_snapshot

    snap = get_trading_mode_snapshot()
    mode = snap.get("effective_mode")
    if mode == "real_armed":
        return snap

    if snap.get("emergency_stop"):
        reason = "EMERGENCY_STOP"
    elif not snap.get("trading_enabled", True):
        reason = "TRADING_ENABLED=false"
    elif snap.get("paper_trading") and not snap.get("force_real_mode"):
        reason = "PAPER_TRADING (use paper path; real create_order forbidden)"
    elif not snap.get("force_real_mode"):
        reason = "FORCE_REAL_MODE not set"
    elif not snap.get("live_gate_signed"):
        reason = "live_gate_unsigned"
    else:
        reason = f"effective_mode={mode}"

    where = f" context={context}" if context else ""
    logger.error("❌ Orden real bloqueada (%s)%s snapshot_mode=%s", reason, where, mode)
    raise RealOrderBlocked(reason, snapshot=snap)


__all__ = ["RealOrderBlocked", "assert_real_order_allowed"]
