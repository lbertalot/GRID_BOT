from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime
from app.services.telegram_alert import send_telegram_alert_async

router = APIRouter(prefix="/api/v1/alerts/telegram", tags=["Alerts"])


@router.post("/critical")
async def telegram_critical_alert(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        message = data.get("message", "Alerta del sistema")
        formatted = f"🚨 ALERTA CRÍTICA\n\n{message}"
        success = await send_telegram_alert_async(formatted)
        if not success:
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": "No se pudo enviar la alerta a Telegram",
                "timestamp": datetime.now().isoformat()
            })
        return JSONResponse(status_code=200, content={
            "status": "success",
            "message": "Alerta enviada correctamente",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })


