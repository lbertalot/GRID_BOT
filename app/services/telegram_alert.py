import os
import requests
import logging

def send_telegram_alert(message: str) -> bool:
    """
    Envía un mensaje de alerta a un chat de Telegram usando el bot configurado por variables de entorno.
    Retorna True si el mensaje fue enviado correctamente, False en caso de error.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    logger = logging.getLogger("telegram_alert")
    if not token or not chat_id:
        logger.error(f"No se encontró TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en las variables de entorno. Mensaje no enviado: {message}")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=5)
        if resp.status_code == 200:
            logger.info(f"Mensaje enviado correctamente por Telegram: {message}")
            return True
        else:
            logger.error(f"Error enviando mensaje por Telegram. Status: {resp.status_code}, Response: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Excepción enviando mensaje por Telegram: {e}. Mensaje: {message}")
        return False 