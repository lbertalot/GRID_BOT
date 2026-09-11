"""Watch CEO de ``system_integrity``: reaviso 6–12h + aviso al cerrar.

No resetea breakers. Paper-only · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

SI_STATE_CHANNEL = "si_state"
SI_HOLD_CTX_CHANNEL = "si_hold_ctx"
_CLOSED_FP = "closed"


@dataclass(frozen=True)
class SiPublicSnapshot:
    active: bool
    public_state: str
    reason: str
    reason_kind: str
    activated_at: str
    fingerprint: str
    ops_inconsistent: bool


def _previous_si_was_open(prev_fp: Optional[str]) -> bool:
    """True solo si hay memoria de SI abierto (no un snapshot cerrado aislado)."""
    text = str(prev_fp or "")
    return text.startswith("open") or text.startswith("system_integrity|True")


def _reason_norm(kind: str) -> str:
    if kind == "trial_nogo":
        return "nogo_idle"
    if kind == "pnl_streak":
        return "pnl_streak"
    if kind == "auth":
        return "auth"
    return "integrity_review"


def _open_event_core(fingerprint: str) -> str:
    text = str(fingerprint or "")
    parts = text.split("|")
    if text.startswith("system_integrity|"):
        return "|".join(parts[:5])
    if text.startswith("open|"):
        return "|".join(parts[:4])
    return text


def _prefer_activated_at(left_fp: str, right_fp: str) -> str:
    left_at = str(left_fp).rsplit("|", 1)[-1]
    right_at = str(right_fp).rsplit("|", 1)[-1]
    if right_at and not left_at:
        return right_fp
    if left_at and not right_at:
        return left_fp
    return right_fp if right_at else left_fp


def normalize_si_public_snapshot(
    *,
    active: Optional[bool] = None,
    in_active_breakers: bool = False,
    operational_state: Optional[str] = None,
    reason: Optional[str] = None,
    activated_at: Optional[str] = None,
    prior_activated_at: Optional[str] = None,
) -> SiPublicSnapshot:
    """Normaliza SI para copy. No muta el breaker ni Redis HASH."""
    from app.core.telegram_ceo_copy import classify_si_reason

    is_active = bool(active) or bool(in_active_breakers)
    raw_ops = str(operational_state or "").strip().upper()
    ops_inconsistent = bool(is_active and raw_ops == "CLOSED")
    if not is_active:
        public_state = "CLOSED"
    elif raw_ops == "REDUCE_ONLY":
        public_state = "OPEN · REDUCE_ONLY"
    else:
        public_state = "OPEN"
    reason_s = str(reason or "")
    kind = classify_si_reason(reason_s)
    stable_at = str(activated_at or "").strip() or str(prior_activated_at or "").strip()
    fingerprint = (
        f"system_integrity|{is_active}|{public_state}|{kind}|"
        f"{_reason_norm(kind)}|{stable_at}"
    )
    return SiPublicSnapshot(
        active=is_active,
        public_state=public_state,
        reason=reason_s,
        reason_kind=kind,
        activated_at=stable_at,
        fingerprint=fingerprint,
        ops_inconsistent=ops_inconsistent,
    )


def _set_ops_inconsistent_gauge(flag: bool) -> None:
    try:
        from app.core.metrics import gridbot_si_ops_state_inconsistent

        gridbot_si_ops_state_inconsistent.set(1.0 if flag else 0.0)
    except Exception:
        pass
    if flag:
        logger.warning(
            "si ops_state inconsistent: active=true operational_state=CLOSED "
            "(copy uses OPEN; breaker not mutated)"
        )


def _si_snapshot(
    breakers: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, str, str]:
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
    operational_state = str(detail.get("operational_state") or "")
    activated_at = str(detail.get("activated_at") or "")
    return si_active, reason, operational_state, activated_at


def process_si_ceo_watch(
    *,
    breakers: Optional[Dict[str, Any]] = None,
    si_open: Optional[bool] = None,
    reason: Optional[str] = None,
    operational_state: Optional[str] = None,
    activated_at: Optional[str] = None,
    historical_streak: Optional[int] = None,
    skip_cleared: bool = False,
    now: Optional[float] = None,
) -> Optional[str]:
    """Devuelve mensaje Telegram CEO o None.

    - SI abierto (no auth) → inmediato al abrir/cambiar fingerprint;
      recordatorio cada ``hold_si_min_repeat_s`` (default 6 h).
    - Transición abierto→cerrado (memoria de estado) → aviso inmediato
      (salvo ``skip_cleared``). Un snapshot cerrado sin abierto previo no avisa.
    """
    from app.core.desk_auto_remediation import is_stale_net_auth_integrity_reason
    from app.core.telegram_ceo_copy import (
        _load_last,
        _save_last,
        ceo_plain_enabled,
        hold_si_min_repeat_s,
        render_hold_pnl_telegram,
        render_si_cleared_telegram,
        should_emit_ceo,
    )

    if not ceo_plain_enabled():
        return None

    ts = time.time() if now is None else now
    hydrate_live = (
        breakers is not None or si_open is None or reason is None
    )
    if hydrate_live:
        try:
            snap_open, snap_reason, snap_ops, snap_at = _si_snapshot(breakers)
        except Exception as exc:
            logger.debug("si snapshot skip: %s", exc)
            snap_open, snap_reason, snap_ops, snap_at = False, "", "", ""
        if si_open is None:
            si_open = snap_open
        if reason is None:
            reason = snap_reason
        if operational_state is None:
            operational_state = snap_ops
        if activated_at is None:
            activated_at = snap_at
    reason = reason or ""
    operational_state = operational_state or ""
    activated_at = activated_at or ""

    ctx = _load_last(SI_HOLD_CTX_CHANNEL)
    prior_at = str(ctx[0] if ctx else "") or ""

    prev = _load_last(SI_STATE_CHANNEL)
    prev_fp = (prev[0] if prev else _CLOSED_FP) or _CLOSED_FP

    if si_open:
        if is_stale_net_auth_integrity_reason(reason):
            _save_last(SI_STATE_CHANNEL, f"open|auth|{reason}", ts)
            return None
        public = normalize_si_public_snapshot(
            active=True,
            in_active_breakers=True,
            operational_state=operational_state,
            reason=reason,
            activated_at=activated_at,
            prior_activated_at=prior_at,
        )
        _set_ops_inconsistent_gauge(public.ops_inconsistent)
        fp = public.fingerprint
        last_hold = _load_last("hold_pnl")
        if last_hold:
            prev_hold_fp, prev_hold_ts = last_hold
            if _open_event_core(prev_hold_fp) == _open_event_core(fp):
                preferred = _prefer_activated_at(prev_hold_fp, fp)
                if preferred != prev_hold_fp:
                    _save_last("hold_pnl", preferred, prev_hold_ts)
                fp = preferred
        if public.activated_at:
            _save_last(SI_HOLD_CTX_CHANNEL, public.activated_at, ts)
        elif "|" in fp:
            tail = fp.rsplit("|", 1)[-1]
            if tail:
                _save_last(SI_HOLD_CTX_CHANNEL, tail, ts)
        _save_last(SI_STATE_CHANNEL, fp, ts)
        if should_emit_ceo(
            "hold_pnl",
            fp,
            min_repeat_s=hold_si_min_repeat_s(),
            now=ts,
        ):
            display_at = public.activated_at or (fp.rsplit("|", 1)[-1] if "|" in fp else "")
            return render_hold_pnl_telegram(
                reason,
                operational_state=public.public_state,
                public_state=public.public_state,
                activated_at=display_at,
                historical_streak=historical_streak,
                now=ts,
            )
        return None

    was_open = _previous_si_was_open(prev_fp)
    _save_last(SI_STATE_CHANNEL, _CLOSED_FP, ts)
    if not was_open or skip_cleared:
        return None
    if "|auth|" in str(prev_fp) or "|auth|" in _open_event_core(prev_fp):
        return None
    if should_emit_ceo("si_cleared", f"cleared|{prev_fp}", force=True, now=ts):
        return render_si_cleared_telegram()
    return None


__all__ = [
    "SI_STATE_CHANNEL",
    "SiPublicSnapshot",
    "normalize_si_public_snapshot",
    "process_si_ceo_watch",
]
