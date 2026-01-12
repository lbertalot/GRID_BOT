import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.services.telegram_alert import send_telegram_alert_async

router = APIRouter(prefix="/api/v1/test", tags=["Test"])


@router.get("/binance")
async def test_binance_connection():
    try:
        # Seguridad CI/CD: deshabilitar por defecto llamadas reales a Binance
        if os.getenv("ALLOW_BINANCE_TEST", "0") != "1":
            return {
                "status": "disabled",
                "message": "Test de Binance deshabilitado en este entorno",
                "timestamp": datetime.now().isoformat()
            }
        from binance import Client
        import asyncio
        
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_SECRET_KEY", "")
        if not api_key or api_secret:
            return {
                "status": "error",
                "message": "API Keys de Binance no configuradas",
                "timestamp": datetime.now().isoformat()
            }
        client = Client(api_key, api_secret)
        
        # ✅ FIX: Get account info (non-blocking)
        account_info = await asyncio.to_thread(client.get_account)
        if 'accountType' in account_info:
            return {
                "status": "success",
                "message": f"Conexión con Binance exitosa - Tipo de cuenta: {account_info['accountType']}",
                "account_type": account_info['accountType'],
                "timestamp": datetime.now().isoformat()
            }
        return {
            "status": "error",
            "message": "Respuesta inesperada de Binance",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error conectando con Binance: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


@router.post("/telegram")
async def test_telegram():
    message = "🤖 GridBot - Mensaje de prueba\n\n✅ Sistema funcionando correctamente"
    try:
        success = await send_telegram_alert_async(message)
        if success:
            return {
                "status": "success",
                "message": "Mensaje de Telegram enviado correctamente",
                "timestamp": datetime.now().isoformat()
            }
        return {
            "status": "error",
            "message": "Error enviando mensaje a Telegram",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error con Telegram: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


