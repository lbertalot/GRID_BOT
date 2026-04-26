import os
import requests
import logging
import aiohttp
import time
import hashlib

_last_sent: dict[str, float] = {}
_cooldown_seconds = int(
    os.getenv("TELEGRAM_COOLDOWN_SECONDS", "600")
)  # 10 min por defecto


def _should_send(msg: str) -> bool:
    now = time.time()
    key = hashlib.sha256(msg.encode("utf-8")).hexdigest()
    last = _last_sent.get(key, 0)
    if now - last < _cooldown_seconds:
        return False
    _last_sent[key] = now
    return True


def send_telegram_alert(message: str) -> bool:
    """
    Envía un mensaje de alerta a un chat de Telegram usando el bot configurado por variables de entorno.
    Retorna True si el mensaje fue enviado correctamente, False en caso de error.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    logger = logging.getLogger("telegram_alert")
    if not token or not chat_id:
        logger.error(
            f"No se encontró TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en las variables de entorno. Mensaje no enviado: {message}"
        )
        return False
    if not _should_send(message):
        logger.info("Telegram dedupe/cooldown: mensaje suprimido")
        return True
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=5)
        if resp.status_code == 200:
            logger.info(f"Mensaje enviado correctamente por Telegram: {message}")
            return True
        else:
            logger.error(
                f"Error enviando mensaje por Telegram. Status: {resp.status_code}, Response: {resp.text}"
            )
            return False
    except Exception as e:
        logger.error(
            f"Excepción enviando mensaje por Telegram: {e}. Mensaje: {message}"
        )
        return False


async def send_telegram_alert_async(message: str) -> bool:
    """
    Versión async de send_telegram_alert para usar en funciones async
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    logger = logging.getLogger("telegram_alert")

    if not token or not chat_id:
        logger.error(
            f"No se encontró TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en las variables de entorno. Mensaje no enviado: {message}"
        )
        return False

    if not _should_send(message):
        logger.info("Telegram dedupe/cooldown (async): mensaje suprimido")
        return True
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, data=payload, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    logger.info(
                        f"Mensaje enviado correctamente por Telegram (async): {message}"
                    )
                    return True
                else:
                    logger.error(
                        f"Error enviando mensaje por Telegram (async). Status: {resp.status}, Response: {await resp.text()}"
                    )
                    return False
    except Exception as e:
        logger.error(
            f"Excepción enviando mensaje por Telegram (async): {e}. Mensaje: {message}"
        )
        return False
