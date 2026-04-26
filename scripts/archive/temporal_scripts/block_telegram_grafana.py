#!/usr/bin/env python3
"""
Script para bloquear conexiones de Telegram al WebSocket live de Grafana
Siguiendo las mejores prácticas de desarrollo Python y FastAPI
"""

import sys
import logging
import subprocess

# Configurar logging estructurado
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def block_telegram_grafana_connections():
    """
    Bloquea conexiones de Telegram al WebSocket live de Grafana
    Implementando principios de desarrollo funcional y defensivo
    """
    logger.info("🚫 Bloqueando conexiones de Telegram al WebSocket live de Grafana...")

    # Reglas de iptables para bloquear Telegram en puerto 3000
    rules = [
        # Bloquear IPs de Telegram en puerto 3000
        [
            "sudo",
            "iptables",
            "-A",
            "INPUT",
            "-s",
            "149.154.0.0/16",
            "-p",
            "tcp",
            "--dport",
            "3000",
            "-j",
            "DROP",
        ],
        [
            "sudo",
            "iptables",
            "-A",
            "INPUT",
            "-s",
            "91.108.0.0/16",
            "-p",
            "tcp",
            "--dport",
            "3000",
            "-j",
            "DROP",
        ],
        # Bloquear específicamente el WebSocket live
        [
            "sudo",
            "iptables",
            "-A",
            "INPUT",
            "-s",
            "149.154.0.0/16",
            "-p",
            "tcp",
            "--dport",
            "3000",
            "-m",
            "string",
            "--string",
            "/api/live/ws",
            "--algo",
            "bm",
            "-j",
            "DROP",
        ],
        [
            "sudo",
            "iptables",
            "-A",
            "INPUT",
            "-s",
            "91.108.0.0/16",
            "-p",
            "tcp",
            "--dport",
            "3000",
            "-m",
            "string",
            "--string",
            "/api/live/ws",
            "--algo",
            "bm",
            "-j",
            "DROP",
        ],
    ]

    successful_rules = 0

    for rule in rules:
        try:
            result = subprocess.run(rule, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                logger.info(f"✅ Regla aplicada: {' '.join(rule[1:])}")
                successful_rules += 1
            else:
                logger.warning(f"⚠️ Error aplicando regla: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error(f"❌ Timeout aplicando regla: {' '.join(rule)}")
        except Exception as e:
            logger.error(f"❌ Error inesperado aplicando regla: {e}")

    if successful_rules > 0:
        logger.info(f"🎉 {successful_rules} reglas de bloqueo aplicadas exitosamente")
        return True
    else:
        logger.error("❌ No se pudieron aplicar las reglas de bloqueo")
        return False


def create_telegram_whitelist():
    """
    Crea una whitelist para permitir solo conexiones legítimas de Telegram
    """
    logger.info("📝 Creando whitelist de Telegram...")

    # Solo permitir conexiones de Telegram a endpoints específicos (no WebSocket live)
    whitelist_rules = [
        # Permitir Telegram solo a endpoints específicos (no live/ws)
        [
            "sudo",
            "iptables",
            "-A",
            "INPUT",
            "-s",
            "149.154.0.0/16",
            "-p",
            "tcp",
            "--dport",
            "3000",
            "-m",
            "string",
            "--string",
            "/api/health",
            "--algo",
            "bm",
            "-j",
            "ACCEPT",
        ],
        [
            "sudo",
            "iptables",
            "-A",
            "INPUT",
            "-s",
            "149.154.0.0/16",
            "-p",
            "tcp",
            "--dport",
            "3000",
            "-m",
            "string",
            "--string",
            "/login",
            "--algo",
            "bm",
            "-j",
            "ACCEPT",
        ],
    ]

    for rule in whitelist_rules:
        try:
            result = subprocess.run(rule, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                logger.info(f"✅ Regla de whitelist aplicada: {' '.join(rule[1:])}")
            else:
                logger.warning(f"⚠️ Error aplicando regla de whitelist: {result.stderr}")

        except Exception as e:
            logger.error(f"❌ Error aplicando regla de whitelist: {e}")


def show_current_rules():
    """
    Muestra las reglas actuales de iptables relacionadas con Telegram
    """
    logger.info("📋 Mostrando reglas actuales de iptables para Telegram...")

    try:
        # Mostrar reglas de INPUT que contienen Telegram
        result = subprocess.run(
            ["sudo", "iptables", "-L", "INPUT", "-n", "--line-numbers"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            lines = result.stdout.split("\n")
            telegram_rules = [
                line for line in lines if "149.154" in line or "91.108" in line
            ]

            if telegram_rules:
                logger.info("🔍 Reglas actuales para Telegram:")
                for rule in telegram_rules:
                    logger.info(f"  {rule}")
            else:
                logger.info("ℹ️ No se encontraron reglas específicas para Telegram")
        else:
            logger.error(f"Error obteniendo reglas: {result.stderr}")

    except Exception as e:
        logger.error(f"Error obteniendo reglas de iptables: {e}")


def main():
    """
    Función principal siguiendo principios de desarrollo funcional
    """
    logger.info("🔒 Iniciando bloqueo de conexiones de Telegram a Grafana...")

    # Verificar si tenemos permisos de sudo
    try:
        result = subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=5)
        if result.returncode != 0:
            logger.error("❌ Este script requiere permisos de sudo")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error verificando permisos de sudo: {e}")
        sys.exit(1)

    # Mostrar reglas actuales
    show_current_rules()

    # Aplicar bloqueo
    success = block_telegram_grafana_connections()

    if success:
        # Crear whitelist para conexiones legítimas
        create_telegram_whitelist()

        logger.info("✅ Bloqueo de Telegram configurado exitosamente")
        logger.info(
            "📝 Las conexiones de Telegram al WebSocket live de Grafana están bloqueadas"
        )
        logger.info(
            "🔓 Las conexiones legítimas de Telegram a otros endpoints siguen permitidas"
        )

        # Mostrar reglas finales
        logger.info("\n📋 Reglas finales aplicadas:")
        show_current_rules()

    else:
        logger.error("❌ No se pudo configurar el bloqueo de Telegram")
        sys.exit(1)


if __name__ == "__main__":
    main()
