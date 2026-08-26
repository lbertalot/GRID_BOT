from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import asyncio
from typing import Any, Dict, List, Optional
from app.services.telegram_alert import send_telegram_alert_async
from app.db.session import SessionLocal
from app.models.alerts import Alert
from app.core.metrics import alerts_persisted_total, pipeline_persistence_failures_total
from app.core.metrics import db_writes_total
from app.core.pipeline_metrics_sidecar import record_db_write
from app.core.telegram_ceo_copy import ceo_plain_enabled, desk_verbose_enabled, format_alertmanager_ceo

router = APIRouter(prefix="/api/v1/alerts/telegram", tags=["Alerts"])


def _ceo_telegram_message(payload: Dict[str, Any], severity: str) -> Optional[str]:
    if ceo_plain_enabled() and not desk_verbose_enabled():
        return format_alertmanager_ceo(payload, severity)
    return _format_alertmanager_message(payload, severity)


def _format_alertmanager_message(payload: Dict[str, Any], severity: str) -> str:
    try:
        alerts: List[Dict[str, Any]] = payload.get("alerts", [])
        if not alerts:
            fallback = (
                payload.get("message") or payload.get("summary") or "Alerta del sistema"
            )
            return f"🚨 ALERTA {severity.upper()}\n\n{fallback}"

        lines: List[str] = [f"🚨 ALERTA {severity.upper()} ({len(alerts)})"]
        for alert in alerts[:5]:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            name = labels.get("alertname", "Unknown")
            inst = labels.get("instance") or labels.get("job") or "N/A"
            sumy = annotations.get("summary") or annotations.get("description") or ""
            starts_at = alert.get("startsAt")
            ends_at = alert.get("endsAt")
            line = (
                f"• {name} @ {inst}\n"
                f"  {sumy}\n"
                f"  inicio: {starts_at or 'n/a'} fin: {ends_at or 'n/a'}"
            )
            lines.append(line)
        if len(alerts) > 5:
            lines.append(f"… y {len(alerts) - 5} más")
        return "\n".join(lines)
    except Exception:
        fallback = payload.get("message") or "Alerta del sistema"
        return f"🚨 ALERTA {severity.upper()}\n\n{fallback}"


def _persist_alert(severity: str, message: str) -> None:
    db = SessionLocal()
    try:
        alert = Alert(
            type="ALERTMANAGER",
            message=message,
            level=severity.upper(),
            sent_to_telegram=False,
        )
        db.add(alert)
        db.commit()
        alerts_persisted_total.labels(severity=severity.lower(), status="ok").inc()
        db_writes_total.labels(table="alerts", operation="insert", status="ok").inc()
        record_db_write(table="alerts", operation="insert", status="ok")
    except Exception:
        db.rollback()
        alerts_persisted_total.labels(severity=severity.lower(), status="error").inc()
        db_writes_total.labels(table="alerts", operation="insert", status="error").inc()
        record_db_write(table="alerts", operation="insert", status="error")
        pipeline_persistence_failures_total.labels(
            table="alerts",
            reason="db_commit_error",
        ).inc()
        raise
    finally:
        db.close()


@router.post("/critical")
async def telegram_critical_alert(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        formatted = _ceo_telegram_message(payload, severity="crítica")
        if formatted is None:
            return JSONResponse(
                status_code=202,
                content={
                    "status": "accepted",
                    "message": "CEO mute (ruido / debounce)",
                    "timestamp": datetime.now().isoformat(),
                },
            )
        _persist_alert(severity="critical", message=formatted)
        asyncio.create_task(send_telegram_alert_async(formatted))
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "message": "Procesamiento en background",
                "timestamp": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


@router.post("/warning")
async def telegram_warning_alert(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        formatted = _ceo_telegram_message(payload, severity="warning")
        if formatted is None:
            return JSONResponse(
                status_code=202,
                content={
                    "status": "accepted",
                    "message": "CEO mute (ruido / debounce)",
                    "timestamp": datetime.now().isoformat(),
                },
            )
        _persist_alert(severity="warning", message=formatted)
        asyncio.create_task(send_telegram_alert_async(formatted))
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "message": "Procesamiento en background",
                "timestamp": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )
