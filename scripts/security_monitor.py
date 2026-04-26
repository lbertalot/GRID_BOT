#!/usr/bin/env python3
"""
Monitor de seguridad para GridBot - Protección contra conexiones externas no autorizadas
Siguiendo las mejores prácticas de desarrollo Python y FastAPI
"""

import os
import time
import logging
import subprocess
from typing import Dict, List, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

# Configurar logging estructurado
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Configuración de seguridad siguiendo patrón RORO"""

    allowed_ips: Set[str]
    blocked_ips: Set[str]
    check_interval: int = 60
    block_threshold: int = 3
    block_duration: int = 3600  # 1 hora


class SecurityMonitor:
    """
    Monitor de seguridad para detectar y bloquear conexiones no autorizadas
    Implementando principios de desarrollo funcional y defensivo
    """

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.suspicious_ips: Dict[str, int] = defaultdict(int)
        self.blocked_ips: Dict[str, datetime] = {}
        self.allowed_ips = config.allowed_ips
        self.blocked_ips_set = config.blocked_ips

    def _get_docker_logs(self, container_name: str, lines: int = 100) -> List[str]:
        """
        Obtiene los logs de Docker con manejo de errores robusto
        """
        try:
            cmd = ["docker", "logs", "--tail", str(lines), container_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return result.stdout.split("\n")
            else:
                logger.error(
                    f"Error obteniendo logs de {container_name}: {result.stderr}"
                )
                return []
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout obteniendo logs de {container_name}")
            return []
        except Exception as e:
            logger.error(f"Error inesperado obteniendo logs de {container_name}: {e}")
            return []

    def _extract_external_ips(self, logs: List[str]) -> Dict[str, int]:
        """
        Extrae IPs externas de los logs
        Implementando parsing defensivo
        """
        external_ips = defaultdict(int)

        for line in logs:
            if "remote_addr=" in line:
                try:
                    # Extraer IP de la línea de log
                    parts = line.split()
                    for part in parts:
                        if "remote_addr=" in part:
                            ip = part.split("=")[1]

                            # Verificar si es IP externa (no localhost, no privada)
                            if self._is_external_ip(ip):
                                external_ips[ip] += 1
                            break
                except Exception as e:
                    logger.warning(f"Error parseando línea de log: {e}")
                    continue

        return external_ips

    def _is_external_ip(self, ip: str) -> bool:
        """
        Verifica si una IP es externa (no local, no privada)
        """
        if ip in self.allowed_ips:
            return False

        if ip in self.blocked_ips_set:
            return False

        # IPs locales y privadas
        local_ips = {"127.0.0.1", "localhost", "::1", "0.0.0.0", "::"}

        if ip in local_ips:
            return False

        # Rangos privados (simplificado)
        if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
            return False

        return True

    def _is_telegram_ip(self, ip: str) -> bool:
        """
        Verifica si una IP pertenece a Telegram
        """
        telegram_ranges = [
            "149.154.",  # Telegram Messenger Inc.
            "91.108.",  # Telegram Messenger Inc.
            "2001:67c:",  # Telegram IPv6
        ]

        for range_prefix in telegram_ranges:
            if ip.startswith(range_prefix):
                return True

        return False

    def _block_ip_iptables(self, ip: str, reason: str) -> bool:
        """
        Bloquea una IP usando iptables
        Implementando manejo de errores anticipado
        """
        try:
            # Bloquear IP usando iptables
            cmd = ["sudo", "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                self.blocked_ips[ip] = datetime.now()
                logger.warning(f"🚫 IP {ip} bloqueada por {reason}")
                return True
            else:
                logger.error(f"Error bloqueando IP {ip}: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout bloqueando IP {ip}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado bloqueando IP {ip}: {e}")
            return False

    def _unblock_ip_iptables(self, ip: str) -> bool:
        """
        Desbloquea una IP
        """
        try:
            # Remover regla de iptables
            cmd = ["sudo", "iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                if ip in self.blocked_ips:
                    del self.blocked_ips[ip]
                logger.info(f"✅ IP {ip} desbloqueada")
                return True
            else:
                logger.warning(f"Advertencia desbloqueando IP {ip}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error desbloqueando IP {ip}: {e}")
            return False

    def _cleanup_expired_blocks(self):
        """
        Limpia bloqueos expirados
        """
        current_time = datetime.now()
        expired_ips = []

        for ip, block_time in self.blocked_ips.items():
            if current_time - block_time > timedelta(
                seconds=self.config.block_duration
            ):
                expired_ips.append(ip)

        for ip in expired_ips:
            self._unblock_ip_iptables(ip)

    def _send_security_alert(self, ip: str, reason: str, count: int):
        """
        Envía alerta de seguridad por Telegram
        """
        try:
            from app.services.telegram_alert import send_telegram_alert

            message = f"""
🚨 **ALERTA DE SEGURIDAD - GridBot**

**IP Externa Detectada:** `{ip}`
**Motivo:** {reason}
**Intentos:** {count}
**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Acción Tomada:** IP bloqueada automáticamente
**Duración del Bloqueo:** {self.config.block_duration // 60} minutos

**Recomendación:** Verificar si esta conexión es legítima
"""

            send_telegram_alert(message)
            logger.info(f"📱 Alerta de seguridad enviada para IP {ip}")

        except Exception as e:
            logger.error(f"Error enviando alerta de seguridad: {e}")

    def monitor_security(self):
        """
        Función principal de monitoreo de seguridad
        Implementando manejo de errores anticipado con guard clauses
        """
        logger.info("🔒 Iniciando monitoreo de seguridad...")

        containers_to_monitor = ["gridbot_grafana", "gridbot_api", "gridbot_prometheus"]

        while True:
            try:
                all_external_ips = defaultdict(int)

                # Monitorear todos los contenedores
                for container in containers_to_monitor:
                    logs = self._get_docker_logs(container)
                    if logs:
                        external_ips = self._extract_external_ips(logs)
                        for ip, count in external_ips.items():
                            all_external_ips[ip] += count

                if not all_external_ips:
                    logger.info("✅ No se detectaron IPs externas")
                else:
                    logger.info(f"🔍 Detectadas {len(all_external_ips)} IPs externas")

                    # Procesar cada IP externa
                    for ip, count in all_external_ips.items():
                        # Verificar si es Telegram
                        if self._is_telegram_ip(ip):
                            logger.warning(
                                f"⚠️ IP de Telegram detectada: {ip} ({count} intentos)"
                            )
                            # Para IPs de Telegram, solo loggear pero no bloquear
                            # ya que podrían ser legítimas
                            continue

                        # Para otras IPs externas, aplicar bloqueo
                        self.suspicious_ips[ip] += count

                        if self.suspicious_ips[ip] >= self.config.block_threshold:
                            reason = f"Intentos sospechosos ({self.suspicious_ips[ip]})"
                            self._block_ip_iptables(ip, reason)
                            self._send_security_alert(
                                ip, reason, self.suspicious_ips[ip]
                            )
                            self.suspicious_ips[ip] = 0  # Reset contador

                # Limpiar bloqueos expirados
                self._cleanup_expired_blocks()

                # Mostrar estado actual
                if self.blocked_ips:
                    logger.info(f"🚫 IPs bloqueadas: {list(self.blocked_ips.keys())}")

                # Esperar antes del siguiente check
                time.sleep(self.config.check_interval)

            except KeyboardInterrupt:
                logger.info("🛑 Monitoreo de seguridad interrumpido por usuario")
                break
            except Exception as e:
                logger.error(f"❌ Error en monitoreo de seguridad: {e}")
                time.sleep(self.config.check_interval)


def main():
    """
    Función principal siguiendo principios de desarrollo funcional
    """
    # IPs permitidas (localhost y rangos privados)
    allowed_ips = {
        "127.0.0.1",
        "localhost",
        "::1",
        "0.0.0.0",
        "::",
        "192.168.0.0/16",
        "10.0.0.0/8",
        "172.16.0.0/12",
    }

    # IPs ya bloqueadas
    blocked_ips = set()

    config = SecurityConfig(
        allowed_ips=allowed_ips,
        blocked_ips=blocked_ips,
        check_interval=int(os.getenv("SECURITY_CHECK_INTERVAL", "60")),
        block_threshold=int(os.getenv("SECURITY_BLOCK_THRESHOLD", "3")),
        block_duration=int(os.getenv("SECURITY_BLOCK_DURATION", "3600")),
    )

    logger.info(f"🔧 Configuración de seguridad: {config.check_interval}s intervalo")

    # Crear instancia del monitor
    monitor = SecurityMonitor(config)

    # Ejecutar monitoreo
    monitor.monitor_security()


if __name__ == "__main__":
    main()
