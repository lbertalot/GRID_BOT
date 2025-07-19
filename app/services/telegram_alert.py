import os
import requests

def send_telegram_alert(message: str) -> bool:
    """
    Envía un mensaje de alerta a un chat de Telegram usando el bot configurado por variables de entorno.
    Retorna True si el mensaje fue enviado correctamente, False en caso de error.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False 