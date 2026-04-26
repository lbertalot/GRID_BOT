from app.core.celery_app import celery_app
import logging
from app.services.telegram_alert import send_telegram_alert

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def send_alert(self, message, level="info"):
    """Envía una alerta"""
    try:
        logger.info(f"Enviando alerta {level}: {message}")

        # Enviar alerta por Telegram si hay configuración
        try:
            send_telegram_alert(f"[{level.upper()}] {message}")
        except Exception:
            pass
        logger.info(f"Alerta enviada: {message}")

        return {"status": "sent", "message": message}

    except Exception as e:
        logger.error(f"Error enviando alerta: {e}")
        raise self.retry(countdown=60, max_retries=3)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def notify_consecutive_api_failures(self, service: str, count: int):
    """Notifica por Telegram cuando hay >3 fallos consecutivos de API."""
    try:
        if count >= 3:
            send_telegram_alert(f"⚠️ {service}: {count} fallos consecutivos de API")
        return {"status": "ok", "service": service, "count": count}
    except Exception as e:
        logger.error(f"Error enviando notificación de fallos consecutivos: {e}")
        raise
