#!/usr/bin/env python3
"""
Monitor y bloqueador de conexiones problemáticas al WebSocket live de Grafana
Siguiendo las mejores prácticas de desarrollo Python y FastAPI
"""

import os
import time
import logging
import subprocess
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta

# Configurar logging estructurado
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class GrafanaMonitorConfig:
    """Configuración del monitor siguiendo patrón RORO"""

    container_name: str
    log_file: str
    block_threshold: int = 5  # Número de errores antes de bloquear
    block_duration: int = 300  # Duración del bloqueo en segundos
    check_interval: int = 60  # Intervalo de verificación en segundos


class GrafanaLiveMonitor:
    """
    Monitor para detectar y bloquear conexiones problemáticas al WebSocket live
    Implementando principios de desarrollo funcional y defensivo
    """

    def __init__(self, config: GrafanaMonitorConfig):
        self.config = config
        self.blocked_ips: Dict[str, datetime] = {}
        self.error_counts: Dict[str, int] = {}

    def _get_docker_logs(self, lines: int = 100) -> List[str]:
        """
        Obtiene los logs de Docker con manejo de errores robusto
        """
        try:
            cmd = ["docker", "logs", "--tail", str(lines), self.config.container_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return result.stdout.split("\n")
            else:
                logger.error(f"Error obteniendo logs: {result.stderr}")
                return []
        except subprocess.TimeoutExpired:
            logger.error("Timeout obteniendo logs de Docker")
            return []
        except Exception as e:
            logger.error(f"Error inesperado obteniendo logs: {e}")
            return []

    def _extract_problematic_ips(self, logs: List[str]) -> Dict[str, int]:
        """
        Extrae IPs problemáticas de los logs
        Implementando parsing defensivo
        """
        problematic_ips = {}

        for line in logs:
            if "live/ws" in line and "status=401" in line and "token.rotate" in line:
                try:
                    # Extraer IP de la línea de log
                    parts = line.split()
                    for part in parts:
                        if "remote_addr=" in part:
                            ip = part.split("=")[1]
                            problematic_ips[ip] = problematic_ips.get(ip, 0) + 1
                            break
                except Exception as e:
                    logger.warning(f"Error parseando línea de log: {e}")
                    continue

        return problematic_ips

    def _is_ip_blocked(self, ip: str) -> bool:
        """
        Verifica si una IP está bloqueada
        """
        if ip not in self.blocked_ips:
            return False

        block_time = self.blocked_ips[ip]
        if datetime.now() - block_time > timedelta(seconds=self.config.block_duration):
            # El bloqueo ha expirado
            del self.blocked_ips[ip]
            return False

        return True

    def _block_ip(self, ip: str) -> bool:
        """
        Bloquea una IP usando iptables
        Implementando manejo de errores anticipado
        """
        if self._is_ip_blocked(ip):
            return True  # Ya está bloqueada

        try:
            # Bloquear IP usando iptables
            cmd = ["sudo", "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                self.blocked_ips[ip] = datetime.now()
                logger.info(f"🚫 IP {ip} bloqueada exitosamente")
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

    def _unblock_ip(self, ip: str) -> bool:
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
            self._unblock_ip(ip)

    def monitor_and_block(self):
        """
        Función principal de monitoreo
        Implementando manejo de errores anticipado con guard clauses
        """
        logger.info("🔍 Iniciando monitoreo de conexiones problemáticas...")

        while True:
            try:
                # Guard clause: verificar que el contenedor existe
                logs = self._get_docker_logs()
                if not logs:
                    logger.warning("⚠️ No se pudieron obtener logs")
                    time.sleep(self.config.check_interval)
                    continue

                # Extraer IPs problemáticas
                problematic_ips = self._extract_problematic_ips(logs)

                if not problematic_ips:
                    logger.info("✅ No se detectaron IPs problemáticas")
                else:
                    logger.info(
                        f"🔍 Detectadas {len(problematic_ips)} IPs problemáticas"
                    )

                    # Procesar cada IP
                    for ip, count in problematic_ips.items():
                        if self._is_ip_blocked(ip):
                            logger.info(f"🚫 IP {ip} ya está bloqueada")
                            continue

                        # Actualizar contador de errores
                        self.error_counts[ip] = self.error_counts.get(ip, 0) + count

                        # Bloquear si supera el umbral
                        if self.error_counts[ip] >= self.config.block_threshold:
                            logger.warning(
                                f"⚠️ IP {ip} superó el umbral ({self.error_counts[ip]} errores)"
                            )
                            self._block_ip(ip)
                            self.error_counts[ip] = 0  # Reset contador

                # Limpiar bloqueos expirados
                self._cleanup_expired_blocks()

                # Mostrar estado actual
                if self.blocked_ips:
                    logger.info(f"🚫 IPs bloqueadas: {list(self.blocked_ips.keys())}")

                # Esperar antes del siguiente check
                time.sleep(self.config.check_interval)

            except KeyboardInterrupt:
                logger.info("🛑 Monitoreo interrumpido por usuario")
                break
            except Exception as e:
                logger.error(f"❌ Error en monitoreo: {e}")
                time.sleep(self.config.check_interval)


def main():
    """
    Función principal siguiendo principios de desarrollo funcional
    """
    # Configuración desde variables de entorno
    config = GrafanaMonitorConfig(
        container_name=os.getenv("GRAFANA_CONTAINER", "gridbot_grafana"),
        log_file=os.getenv("GRAFANA_LOG_FILE", "/var/log/grafana/grafana.log"),
        block_threshold=int(os.getenv("BLOCK_THRESHOLD", "5")),
        block_duration=int(os.getenv("BLOCK_DURATION", "300")),
        check_interval=int(os.getenv("CHECK_INTERVAL", "60")),
    )

    logger.info(f"🔧 Configuración: {config.container_name}")

    # Crear instancia del monitor
    monitor = GrafanaLiveMonitor(config)

    # Ejecutar monitoreo
    monitor.monitor_and_block()


if __name__ == "__main__":
    main()
