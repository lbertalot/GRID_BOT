from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import asyncio
from typing import Any, Dict, List
from app.services.telegram_alert import send_telegram_alert_async

router = APIRouter(prefix="/api/v1/alerts/telegram", tags=["Alerts"])


def _format_alertmanager_message(payload: Dict[str, Any], severity: str) -> str:
    try:
        alerts: List[Dict[str, Any]] = payload.get("alerts", [])
        if not alerts:
            fallback = payload.get("message") or payload.get("summary") or "Alerta del sistema"
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


@router.post("/critical")
async def telegram_critical_alert(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        formatted = _format_alertmanager_message(payload, severity="crítica")
        asyncio.create_task(send_telegram_alert_async(formatted))
        return JSONResponse(status_code=202, content={
            "status": "accepted",
            "message": "Procesamiento en background",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


@router.post("/warning")
async def telegram_warning_alert(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        formatted = _format_alertmanager_message(payload, severity="warning")
        asyncio.create_task(send_telegram_alert_async(formatted))
        return JSONResponse(status_code=202, content={
            "status": "accepted",
            "message": "Procesamiento en background",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


