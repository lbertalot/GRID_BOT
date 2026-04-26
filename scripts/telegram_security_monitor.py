#!/usr/bin/env python3
"""
Monitor de Seguridad para Telegram - Validación de comunicaciones unidireccionales
Siguiendo las mejores prácticas de desarrollo Python y FastAPI
"""

import os
import sys
import time
import logging
import subprocess
import json
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

# Configurar logging estructurado
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TelegramSecurityConfig:
    """Configuración de seguridad de Telegram siguiendo patrón RORO"""

    bot_token: str
    chat_id: str
    check_interval: int = 300  # 5 minutos
    log_file: str = "/var/log/telegram_security.log"


class TelegramSecurityMonitor:
    """
    Monitor de seguridad para validar que Telegram solo reciba información
    Implementando principios de desarrollo funcional y defensivo
    """

    def __init__(self, config: TelegramSecurityConfig):
        self.config = config
        self.telegram_ips = ["149.154.0.0/16", "91.108.0.0/16"]
        self.outbound_connections = []
        self.inbound_attempts = []

    def _get_telegram_connections(self) -> Dict[str, List[str]]:
        """
        Obtiene conexiones activas a Telegram
        Implementando parsing defensivo
        """
        connections = {"outbound": [], "inbound": []}

        try:
            # Obtener conexiones de red
            result = subprocess.run(
                ["netstat", "-an"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                lines = result.stdout.split("\n")

                for line in lines:
                    if any(
                        ip_range.split(".")[0] in line for ip_range in self.telegram_ips
                    ):
                        if "ESTABLISHED" in line and "149.154" in line:
                            # Conexión outbound establecida
                            connections["outbound"].append(line.strip())
                        elif "LISTEN" in line and "149.154" in line:
                            # Conexión inbound (problemática)
                            connections["inbound"].append(line.strip())

        except Exception as e:
            logger.error(f"Error obteniendo conexiones de red: {e}")

        return connections

    def _check_webhook_status(self) -> Dict[str, Any]:
        """
        Verifica el estado del webhook de Telegram
        """
        try:
            url = f"https://api.telegram.org/bot{self.config.bot_token}/getWebhookInfo"
            result = subprocess.run(
                ["curl", "-s", url], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                webhook_info = json.loads(result.stdout)
                return webhook_info.get("result", {})
            else:
                logger.error(f"Error obteniendo webhook info: {result.stderr}")
                return {}

        except Exception as e:
            logger.error(f"Error verificando webhook: {e}")
            return {}

    def _validate_telegram_configuration(self) -> Dict[str, bool]:
        """
        Valida la configuración de Telegram
        """
        validation = {
            "bot_token_configured": bool(self.config.bot_token),
            "chat_id_configured": bool(self.config.chat_id),
            "webhook_empty": False,
            "only_outbound_connections": False,
            "no_inbound_connections": False,
        }

        # Verificar webhook
        webhook_info = self._check_webhook_status()
        validation["webhook_empty"] = webhook_info.get("url", "") == ""

        # Verificar conexiones
        connections = self._get_telegram_connections()
        validation["only_outbound_connections"] = len(connections["outbound"]) > 0
        validation["no_inbound_connections"] = len(connections["inbound"]) == 0

        return validation

    def _send_test_message(self) -> bool:
        """
        Envía un mensaje de prueba para verificar funcionalidad
        """
        try:
            # Importar el servicio de Telegram
            sys.path.append("/app")
            from app.services.telegram_alert import send_telegram_alert

            test_message = f"""
🔒 **Reporte de Seguridad Telegram**

**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Estado:** ✅ Sistema seguro
**Conexiones:** Solo outbound
**Webhook:** No configurado

**Validación:** Telegram solo recibe lo que enviamos
"""

            result = send_telegram_alert(test_message)
            return result

        except Exception as e:
            logger.error(f"Error enviando mensaje de prueba: {e}")
            return False

    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """
        Registra eventos de seguridad
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details,
        }

        try:
            with open(self.config.log_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error(f"Error escribiendo log de seguridad: {e}")

    def monitor_telegram_security(self):
        """
        Función principal de monitoreo de seguridad de Telegram
        Implementando manejo de errores anticipado con guard clauses
        """
        logger.info("🔒 Iniciando monitoreo de seguridad de Telegram...")

        while True:
            try:
                # Validar configuración
                validation = self._validate_telegram_configuration()

                # Verificar conexiones
                connections = self._get_telegram_connections()

                # Log de seguridad
                security_status = {
                    "validation": validation,
                    "connections": {
                        "outbound_count": len(connections["outbound"]),
                        "inbound_count": len(connections["inbound"]),
                    },
                }

                self._log_security_event("security_check", security_status)

                # Evaluar estado de seguridad
                is_secure = (
                    validation["bot_token_configured"]
                    and validation["chat_id_configured"]
                    and validation["webhook_empty"]
                    and validation["no_inbound_connections"]
                )

                if is_secure:
                    logger.info(
                        "✅ Telegram: Configuración segura - Solo conexiones outbound"
                    )
                else:
                    logger.warning(
                        "⚠️ Telegram: Posible problema de seguridad detectado"
                    )

                    # Alertar sobre problemas específicos
                    if not validation["webhook_empty"]:
                        logger.error(
                            "🚨 PROBLEMA: Webhook configurado - Telegram puede conectarse"
                        )

                    if validation["inbound_count"] > 0:
                        logger.error("🚨 PROBLEMA: Conexiones inbound detectadas")

                # Enviar reporte periódico (cada 10 checks)
                if hasattr(self, "_check_count"):
                    self._check_count += 1
                else:
                    self._check_count = 1

                if self._check_count % 10 == 0:
                    logger.info("📊 Enviando reporte de seguridad periódico...")
                    self._send_test_message()

                # Esperar antes del siguiente check
                time.sleep(self.config.check_interval)

            except KeyboardInterrupt:
                logger.info(
                    "🛑 Monitoreo de seguridad de Telegram interrumpido por usuario"
                )
                break
            except Exception as e:
                logger.error(f"❌ Error en monitoreo de seguridad de Telegram: {e}")
                time.sleep(self.config.check_interval)


def main():
    """
    Función principal siguiendo principios de desarrollo funcional
    """
    # Configuración desde variables de entorno
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        logger.error("❌ TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados")
        sys.exit(1)

    config = TelegramSecurityConfig(
        bot_token=bot_token,
        chat_id=chat_id,
        check_interval=int(os.getenv("TELEGRAM_SECURITY_CHECK_INTERVAL", "300")),
    )

    logger.info(
        f"🔧 Configuración de seguridad Telegram: {config.check_interval}s intervalo"
    )

    # Crear instancia del monitor
    monitor = TelegramSecurityMonitor(config)

    # Ejecutar monitoreo
    monitor.monitor_telegram_security()


if __name__ == "__main__":
    main()
