"""Celery tasks — desk hourly CEO digest + EOD day-N+1 action plan.

Paper-safe. Opt-in: DESK_HOURLY_STATUS_ENABLED=true.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _telegram(message: str) -> bool:
    try:
        from app.services.telegram_alert import send_telegram_alert

        return bool(send_telegram_alert(message))
    except Exception as exc:  # pragma: no cover
        logger.warning("Telegram desk status no enviado: %s", exc)
        return False


@celery_app.task(name="app.services.desk_status_tasks.send_desk_hourly_digest")
def send_desk_hourly_digest() -> Dict[str, Any]:
    """Cada hora (:05 UTC): digest CEO + bloques área → Telegram."""
    from app.core.desk_hourly_status import build_live_digest, is_enabled

    if not is_enabled():
        logger.info("desk hourly status disabled (DESK_HOURLY_STATUS_ENABLED)")
        return {"ok": False, "reason": "disabled"}

    digest = build_live_digest()
    payload = digest.full_telegram_payload(include_area_blocks=False)
    sent = _telegram(payload)
    logger.info(
        "desk hourly digest day=%s global=%s sent=%s",
        digest.day_n,
        digest.global_status,
        sent,
    )
    return {
        "ok": True,
        "sent": sent,
        "day_n": digest.day_n,
        "global_status": digest.global_status,
        "effective_mode": digest.effective_mode,
        "equity_last": digest.equity_last,
        "chars": len(payload),
    }


@celery_app.task(name="app.services.desk_status_tasks.send_desk_eod_day_plan")
def send_desk_eod_day_plan() -> Dict[str, Any]:
    """Post-cierre (~00:45 UTC): escribe action plan Día N+1 + resumen Telegram."""
    from app.core.desk_hourly_status import (
        build_live_digest,
        is_enabled,
        write_day2_action_plan,
    )

    if not is_enabled():
        return {"ok": False, "reason": "disabled"}

    digest = build_live_digest()
    path = write_day2_action_plan(digest)
    summary = (
        f"📋 EOD PLAN | Día {digest.day_n}→{min(30, digest.day_n + 1)}/30\n"
        f"Veredicto día: {digest.global_status}\n"
        f"Archivo: {path}\n"
        f"E_last={digest.equity_last or 'UNAVAILABLE'} mode={digest.effective_mode}\n"
        f"PROMOTE_LIVE: NO · paper-only"
    )
    sent = _telegram(summary)
    return {
        "ok": True,
        "sent": sent,
        "path": str(path),
        "day_n": digest.day_n,
        "global_status": digest.global_status,
    }
