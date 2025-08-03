from app.core.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def send_alert(self, message, level="info"):
    """Envía una alerta"""
    try:
        logger.info(f"Enviando alerta {level}: {message}")
        
        # TODO: Implementar envío de alertas real (Telegram, email, etc.)
        logger.info(f"Alerta enviada: {message}")
        
        return {"status": "sent", "message": message}
        
    except Exception as e:
        logger.error(f"Error enviando alerta: {e}")
        raise self.retry(countdown=60, max_retries=3) 