"""Celery tasks — desk hourly CEO digest + EOD day-N+1 action plan.

Paper-safe. Opt-in: DESK_HOURLY_STATUS_ENABLED=true.

Antes del digest: auto-remediación paper de ``system_integrity`` stale
(DESK_AUTO_REMEDIATE_BREAKERS, default true) para no depender de paste Telegram.
EOD: escribe tear Capa A automático (AS-1).
Digest: acciones por área AT_RISK/OFF_TRACK (AS-2).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _telegram(message: str) -> bool:
    try:
        from app.services.telegram_alert import send_telegram_alert

        return bool(send_telegram_alert(message))
    except Exception as exc:  # pragma: no cover
        logger.warning("Telegram desk status no enviado: %s", exc)
        return False


def _run_auto_remediation() -> Dict[str, Any]:
    """Ejecuta remediación paper y avisa Telegram si actuó o hold validate."""
    try:
        from app.core.desk_auto_remediation import (
            format_remediation_telegram,
            maybe_remediate_stale_system_integrity,
        )
        from app.core.telegram_ceo_copy import (
            HOLD_PNL_MIN_REPEAT_S,
            ceo_plain_enabled,
            hold_kind_from_remediation,
            should_emit_ceo,
        )

        result = maybe_remediate_stale_system_integrity()
        note = format_remediation_telegram(result)
        if note:
            send = True
            if ceo_plain_enabled():
                kind = hold_kind_from_remediation(result)
                if result.get("acted"):
                    send = should_emit_ceo(
                        "remediated",
                        f"acted|{result.get('action')}",
                        force=True,
                    )
                elif kind == "pnl":
                    send = should_emit_ceo(
                        "hold_pnl",
                        f"pnl|{result.get('breaker_reason') or ''}",
                        min_repeat_s=HOLD_PNL_MIN_REPEAT_S,
                    )
                elif kind == "auth":
                    send = should_emit_ceo(
                        "hold_auth",
                        "auth",
                        min_repeat_s=HOLD_PNL_MIN_REPEAT_S,
                    )
            if send:
                _telegram(note)
        logger.info(
            "desk auto-remediate acted=%s action=%s reason=%s",
            result.get("acted"),
            result.get("action"),
            result.get("reason"),
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("desk auto-remediate error (non-fatal): %s", exc)
        return {"acted": False, "action": "error", "reason": str(exc)}


def _run_area_actions(digest: Any, remediation: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        from app.core.desk_area_actions import (
            format_actions_telegram,
            plan_actions_for_areas,
        )

        actions = plan_actions_for_areas(
            getattr(digest, "areas", None) or [],
            remediation=remediation,
        )
        note = format_actions_telegram(actions)
        if note:
            _telegram(note)
        return [
            {
                "code": a.code,
                "status": a.status,
                "owner": a.owner,
                "action": a.action,
                "auto": a.auto,
            }
            for a in actions
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("desk area actions error (non-fatal): %s", exc)
        return []


def _run_tear_capa_a() -> Optional[str]:
    try:
        from app.core.desk_tear_capa_a import write_tear_capa_a

        path = write_tear_capa_a()
        return str(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("tear Capa A EOD error (non-fatal): %s", exc)
        return None


@celery_app.task(name="app.services.desk_status_tasks.send_desk_hourly_digest")
def send_desk_hourly_digest() -> Dict[str, Any]:
    """Cada hora (:05 UTC): auto-remediate → digest → acciones área → Telegram."""
    from app.core.desk_hourly_status import build_live_digest, is_enabled

    if not is_enabled():
        logger.info("desk hourly status disabled (DESK_HOURLY_STATUS_ENABLED)")
        return {"ok": False, "reason": "disabled"}

    remediation = _run_auto_remediation()
    digest = build_live_digest()
    area_actions = _run_area_actions(digest, remediation)
    payload = digest.full_telegram_payload(include_area_blocks=False)
    sent = False
    from app.core.telegram_ceo_copy import (
        SEMAFORO_ROJO_SISTEMA,
        ceo_plain_enabled,
        ceo_semaforo,
        digest_fingerprint,
        hold_kind_from_remediation,
        should_emit_ceo,
    )

    if ceo_plain_enabled():
        fp = digest_fingerprint(
            digest, hold_kind=hold_kind_from_remediation(remediation)
        )
        if should_emit_ceo(
            "digest",
            fp,
            force=ceo_semaforo(digest) == SEMAFORO_ROJO_SISTEMA,
        ):
            sent = _telegram(payload)
    else:
        sent = _telegram(payload)
    logger.info(
        "desk hourly digest day=%s global=%s sent=%s remediated=%s actions=%s",
        digest.day_n,
        digest.global_status,
        sent,
        remediation.get("acted"),
        len(area_actions),
    )
    return {
        "ok": True,
        "sent": sent,
        "day_n": digest.day_n,
        "global_status": digest.global_status,
        "effective_mode": digest.effective_mode,
        "equity_last": digest.equity_last,
        "chars": len(payload),
        "remediation": remediation,
        "area_actions": area_actions,
    }


@celery_app.task(name="app.services.desk_status_tasks.send_desk_eod_day_plan")
def send_desk_eod_day_plan() -> Dict[str, Any]:
    """Post-cierre (~00:45 UTC): remedia → tear Capa A → day plan → Telegram."""
    from app.core.desk_hourly_status import (
        build_live_digest,
        is_enabled,
        write_day2_action_plan,
    )

    if not is_enabled():
        return {"ok": False, "reason": "disabled"}

    remediation = _run_auto_remediation()
    digest = build_live_digest()
    area_actions = _run_area_actions(digest, remediation)
    tear_path = _run_tear_capa_a()
    path = write_day2_action_plan(digest)
    from app.core.telegram_ceo_copy import (
        ceo_plain_enabled,
        digest_fingerprint,
        hold_kind_from_remediation,
        render_eod_ceo,
        should_emit_ceo,
    )

    if ceo_plain_enabled():
        fp = digest_fingerprint(
            digest, hold_kind=hold_kind_from_remediation(remediation)
        )
        should_emit_ceo("digest", fp, force=True)
        summary = render_eod_ceo(digest, tear_ok=bool(tear_path))
    else:
        summary = (
            f"📋 EOD PLAN | Día {digest.day_n}→{min(30, digest.day_n + 1)}/30\n"
            f"Veredicto día: {digest.global_status}\n"
            f"Tear Capa A: {tear_path or 'UNAVAILABLE'}\n"
            f"Archivo: {path}\n"
            f"E_last={digest.equity_last or 'UNAVAILABLE'} mode={digest.effective_mode}\n"
            f"Auto-remediate: acted={remediation.get('acted')} "
            f"action={remediation.get('action')}\n"
            f"Area actions: {len(area_actions)}\n"
            f"PROMOTE_LIVE: NO · paper-only"
        )
    sent = _telegram(summary)
    return {
        "ok": True,
        "sent": sent,
        "path": str(path),
        "tear_path": tear_path,
        "day_n": digest.day_n,
        "global_status": digest.global_status,
        "remediation": remediation,
        "area_actions": area_actions,
    }
