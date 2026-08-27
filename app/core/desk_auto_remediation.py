"""Auto-remediación desk paper — actúa en digests AT_RISK sin intervención humana.

Caso P0 (reincidente): ``system_integrity`` stale por ``binance_net_fail`` /
``binance_auth_fail`` cuando validate ya está OK → deactivate paper-safe.

Paper-only. Kill switch: ``DESK_AUTO_REMEDIATE_BREAKERS=false``.
Nunca toca live / FORCE_REAL / sizing.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AUTO_REMEDIATE_ENV = "DESK_AUTO_REMEDIATE_BREAKERS"
STALE_INTEGRITY_REASONS = frozenset(
    {"binance_net_fail", "binance_auth_fail", "binance_net", "binance_auth"}
)


def is_stale_net_auth_integrity_reason(reason: Any) -> bool:
    """True sólo para razones net/auth stale. PnL / IC-2 / vacío → False."""
    return str(reason or "").strip().lower() in STALE_INTEGRITY_REASONS


def auto_remediate_enabled() -> bool:
    return os.getenv(AUTO_REMEDIATE_ENV, "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _is_paper_sot() -> bool:
    try:
        from app.core.paper_equity_ledger import paper_equity_is_source_of_truth

        return bool(paper_equity_is_source_of_truth())
    except Exception:
        return os.getenv("PAPER_TRADING", "false").lower() == "true"


def _breaker_snapshot() -> Dict[str, Any]:
    from app.core.circuit_breakers import get_shared_breakers

    ck = get_shared_breakers()
    return ck.get_all_breakers_status() if hasattr(ck, "get_all_breakers_status") else {}


def _validate_binance() -> Dict[str, Any]:
    from app.services.binance_client_singleton import get_binance_client_singleton

    return get_binance_client_singleton().validate_credentials_and_connectivity()


def maybe_remediate_stale_system_integrity(
    *,
    validate: Optional[Dict[str, Any]] = None,
    breakers: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Intenta cerrar ``system_integrity`` stale en paper.

    Returns dict con keys: ``acted``, ``action``, ``reason``, ``details``.
    """
    moment = datetime.now(timezone.utc).isoformat()
    if not auto_remediate_enabled():
        return {
            "acted": False,
            "action": "skipped",
            "reason": f"{AUTO_REMEDIATE_ENV}=false",
            "at": moment,
        }
    if not _is_paper_sot():
        return {
            "acted": False,
            "action": "skipped",
            "reason": "not_paper_sot",
            "at": moment,
        }

    bs = breakers if breakers is not None else _breaker_snapshot()
    active: List[str] = list(bs.get("active_breakers") or [])
    detail = (bs.get("breakers") or {}).get("system_integrity") or {}
    si_active = bool(detail.get("active")) or ("system_integrity" in active)
    si_reason = str(detail.get("reason") or "")

    if not si_active:
        return {
            "acted": False,
            "action": "none",
            "reason": "system_integrity_closed",
            "at": moment,
            "active_breakers": active,
        }

    check = validate if validate is not None else _validate_binance()
    auth_ok = bool(check.get("auth_ok"))
    net_ok = bool(check.get("net_ok"))
    if not (auth_ok and net_ok):
        return {
            "acted": False,
            "action": "hold",
            "reason": "validate_not_ok",
            "at": moment,
            "validate": {"auth_ok": auth_ok, "net_ok": net_ok},
            "breaker_reason": si_reason,
            "active_breakers": active,
        }

    # Solo auto-clear razones de net/auth conocidas (stale post-allowlist).
    # Nunca resetear breakers de trading/PnL (p.ej. pérdidas consecutivas, IC-2):
    # validate auth/net OK no implica que el riesgo de mercado haya desaparecido.
    if not is_stale_net_auth_integrity_reason(si_reason):
        logger.info(
            "desk auto-remediate: refuse reason=%r (solo net/auth stale)",
            si_reason,
        )
        return {
            "acted": False,
            "action": "hold_trading_reason",
            "reason": "reason_not_stale_net_auth",
            "at": moment,
            "validate": {"auth_ok": auth_ok, "net_ok": net_ok},
            "breaker_reason": si_reason,
            "active_breakers": active,
        }

    try:
        import asyncio

        from app.core.circuit_breakers import get_shared_breakers

        ck = get_shared_breakers()
        deactivate = getattr(ck, "deactivate_breaker", None)
        if deactivate is None:
            return {
                "acted": False,
                "action": "error",
                "reason": "no_deactivate",
                "at": moment,
            }
        if asyncio.iscoroutinefunction(deactivate):
            asyncio.run(deactivate("system_integrity"))
        else:
            deactivate("system_integrity")
    except Exception as exc:
        logger.warning("desk auto-remediate deactivate failed: %s", exc)
        return {
            "acted": False,
            "action": "error",
            "reason": str(exc),
            "at": moment,
        }

    bs_after = _breaker_snapshot()
    still = "system_integrity" in (bs_after.get("active_breakers") or [])
    return {
        "acted": not still,
        "action": "reset_system_integrity",
        "reason": "stale_after_validate_ok",
        "at": moment,
        "breaker_reason_before": si_reason,
        "validate": {"auth_ok": auth_ok, "net_ok": net_ok, "ok": check.get("ok")},
        "active_breakers_after": list(bs_after.get("active_breakers") or []),
    }


def format_remediation_telegram(result: Dict[str, Any]) -> Optional[str]:
    """Mensaje corto post-acción (None si no hay que avisar)."""
    from app.core.telegram_ceo_copy import (
        ceo_plain_enabled,
        render_hold_auth_telegram,
        render_remediated_telegram,
    )

    if not result.get("acted"):
        if result.get("action") == "hold":
            if ceo_plain_enabled():
                return render_hold_auth_telegram()
            return (
                "🛠️ DESK AUTO · HOLD\n"
                f"system_integrity abierto; validate no OK "
                f"(auth={result.get('validate', {}).get('auth_ok')} "
                f"net={result.get('validate', {}).get('net_ok')}).\n"
                "Revisar IP allowlist Binance. PROMOTE_LIVE: NO"
            )
        if result.get("action") == "hold_trading_reason":
            if ceo_plain_enabled():
                # Heartbeat 1h + aviso al cerrar: `breaker_ceo_watch`.
                return None
            return (
                "🛠️ DESK AUTO · HOLD (no auto-clear)\n"
                f"system_integrity por razón de trading/PnL: "
                f"{result.get('breaker_reason') or 'n/a'}.\n"
                "Validate auth/net OK no autoriza reset. "
                "Owner: RISK + MM (RCA). PROMOTE_LIVE: NO · paper-only"
            )
        return None
    if ceo_plain_enabled():
        return render_remediated_telegram()
    return (
        "🛠️ DESK AUTO · REMEDIADO\n"
        "Reset paper-safe `system_integrity` "
        f"(antes: {result.get('breaker_reason_before') or 'n/a'}) "
        "tras validate auth_ok+net_ok.\n"
        f"active_after={result.get('active_breakers_after')}\n"
        "PROMOTE_LIVE: NO · paper-only"
    )


__all__ = [
    "AUTO_REMEDIATE_ENV",
    "auto_remediate_enabled",
    "maybe_remediate_stale_system_integrity",
    "format_remediation_telegram",
]
