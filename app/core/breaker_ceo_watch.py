"""Watch CEO de ``system_integrity``: heartbeat 1h en HOLD PnL + aviso al cerrar.

No resetea breakers. Paper-only · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SI_STATE_CHANNEL = "si_state"


def _si_snapshot(
    breakers: Optional[Dict[str, Any]] = None,
) -> tuple[bool, str]:
    if breakers is None:
        from app.core.circuit_breakers import get_shared_breakers

        ck = get_shared_breakers()
        breakers = (
            ck.get_all_breakers_status()
            if hasattr(ck, "get_all_breakers_status")
            else {}
        )
    active = list(breakers.get("active_breakers") or [])
    detail = (breakers.get("breakers") or {}).get("system_integrity") or {}
    # API list-style: breakers puede ser lista de dicts
    if isinstance(breakers.get("breakers"), list):
        for row in breakers["breakers"]:
            if isinstance(row, dict) and row.get("name") == "system_integrity":
                detail = row
                break
        si_active = str(detail.get("state") or "").lower() == "open" or (
            "system_integrity" in active
        )
    else:
        si_active = bool(detail.get("active")) or ("system_integrity" in active)
    reason = str(detail.get("reason") or "")
    return si_active, reason


def process_si_ceo_watch(
    *,
    breakers: Optional[Dict[str, Any]] = None,
    si_open: Optional[bool] = None,
    reason: Optional[str] = None,
    skip_cleared: bool = False,
    now: Optional[float] = None,
) -> Optional[str]:
    """Devuelve mensaje Telegram CEO o None.

    - SI abierto por PnL/trading → heartbeat cada ``HOLD_PNL_MIN_REPEAT_S``.
    - Transición abierto→cerrado → aviso inmediato (salvo ``skip_cleared``).
    """
    from app.core.desk_auto_remediation import is_stale_net_auth_integrity_reason
    from app.core.telegram_ceo_copy import (
        HOLD_PNL_MIN_REPEAT_S,
        _load_last,
        _save_last,
        ceo_plain_enabled,
        render_hold_pnl_telegram,
        render_si_cleared_telegram,
        should_emit_ceo,
    )

    if not ceo_plain_enabled():
        return None

    ts = time.time() if now is None else now
    if si_open is None or reason is None:
        live_open, live_reason = _si_snapshot(breakers)
        if si_open is None:
            si_open = live_open
        if reason is None:
            reason = live_reason
    reason = reason or ""

    prev = _load_last(SI_STATE_CHANNEL)
    prev_fp = (prev[0] if prev else "closed") or "closed"

    if si_open:
        if is_stale_net_auth_integrity_reason(reason):
            _save_last(SI_STATE_CHANNEL, f"open|auth|{reason}", ts)
            return None
        fp = f"open|pnl|{reason}"
        _save_last(SI_STATE_CHANNEL, fp, ts)
        if should_emit_ceo(
            "hold_pnl",
            fp,
            min_repeat_s=HOLD_PNL_MIN_REPEAT_S,
            now=ts,
        ):
            return render_hold_pnl_telegram(reason)
        return None

    was_open = str(prev_fp).startswith("open")
    _save_last(SI_STATE_CHANNEL, "closed", ts)
    if not was_open or skip_cleared:
        return None
    # Conexión: el copy ``remediated`` ya avisó.
    if "|auth|" in str(prev_fp):
        return None
    if should_emit_ceo("si_cleared", f"cleared|{prev_fp}", force=True, now=ts):
        return render_si_cleared_telegram()
    return None


__all__ = ["SI_STATE_CHANNEL", "process_si_ceo_watch"]
