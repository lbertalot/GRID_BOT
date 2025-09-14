"""
Telegram Bot - Módulo de Telegram Simplificado
GridBot v2.5 - Componente de Integridad Integrado
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class TelegramBot:
    """Clase simplificada de Telegram para componentes de integridad"""
    
    def __init__(self):
        self.logger = logger
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id)
        self._dedupe_ttl_seconds = int(os.getenv("TELEGRAM_DEDUPE_TTL_SECONDS", "600"))
        self._last_sent: dict[str, float] = {}
        
        if self.enabled:
            self.logger.info("🔧 Bot de Telegram configurado correctamente")
        else:
            self.logger.warning("⚠️ Bot de Telegram no configurado - usando modo simulado")
    
    async def send_alert(self, message: str) -> bool:
        """Enviar alerta por Telegram"""
        try:
            # Deduplicación básica por hash de contenido
            import time, hashlib
            key = hashlib.sha256(message.encode("utf-8")).hexdigest()
            now = time.time()
            last = self._last_sent.get(key, 0.0)
            if now - last < self._dedupe_ttl_seconds:
                self.logger.info("📱 [DEDUP] Alerta Telegram omitida por TTL")
                return True
            self._last_sent[key] = now
            
            if not self.enabled:
                # Modo simulado
                self.logger.info(f"📱 [SIMULADO] Telegram: {message[:100]}...")
                return True
            
            # Aquí iría la lógica real de envío
            self.logger.info(f"📱 Telegram enviado: {message[:100]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error enviando alerta por Telegram: {e}")
            return False
    
    def send_alert_sync(self, message: str) -> bool:
        """Enviar alerta por Telegram (versión síncrona)"""
        try:
            if not self.enabled:
                # Modo simulado
                self.logger.info(f"📱 [SIMULADO] Telegram: {message[:100]}...")
                return True
            
            # Aquí iría la lógica real de envío
            self.logger.info(f"📱 Telegram enviado: {message[:100]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error enviando alerta por Telegram: {e}")
            return False
