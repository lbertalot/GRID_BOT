from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
from app.services.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)

def sanitize_error_message(error_detail: str) -> str:
    """
    Sanitiza mensajes de error para no exponer información sensible.
    """
    # Lista de patrones sensibles que no deben aparecer en errores
    sensitive_patterns = [
        'api_key', 'api_secret', 'password', 'token', 'secret',
        'private', 'key', 'credential', 'auth'
    ]
    
    error_lower = error_detail.lower()
    for pattern in sensitive_patterns:
        if pattern in error_lower:
            return "Error de configuración o autenticación"
    
    return error_detail

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Maneja errores de validación de Pydantic de forma segura.
    """
    error_details = []
    for error in exc.errors():
        field = error.get('loc', ['unknown'])[-1]
        message = sanitize_error_message(str(error.get('msg', 'Error de validación')))
        error_details.append(f"{field}: {message}")
    
    error_message = "; ".join(error_details)
    logger.warning(f"Error de validación en {request.url}: {error_message}")
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "Datos de entrada inválidos",
            "details": error_details
        }
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Maneja excepciones HTTP de forma segura.
    """
    error_message = sanitize_error_message(exc.detail)
    logger.error(f"Error HTTP {exc.status_code} en {request.url}: {error_message}")
    
    # Enviar alerta para errores críticos
    if exc.status_code >= 500:
        send_telegram_alert(f"🚨 Error crítico en la API: {exc.status_code} - {error_message}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Error en el servidor" if exc.status_code >= 500 else "Error en la solicitud",
            "message": error_message
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """
    Maneja excepciones generales de forma segura.
    """
    error_message = sanitize_error_message(str(exc))
    logger.error(f"Error no manejado en {request.url}: {error_message}", exc_info=True)
    
    # Enviar alerta para errores no manejados
    send_telegram_alert(f"🚨 Error no manejado en la API: {error_message}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "message": "Ha ocurrido un error inesperado"
        }
    ) 