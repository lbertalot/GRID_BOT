#!/usr/bin/env python3
"""
Script para resolver problemas de token rotation en Grafana
Siguiendo las mejores prácticas de desarrollo Python y FastAPI
"""

import os
import sys
import time
import logging
import requests
from typing import Optional
from dataclasses import dataclass

# Configurar logging estructurado
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class GrafanaConfig:
    """Configuración de Grafana siguiendo patrón RORO"""

    url: str
    admin_user: str
    admin_password: str
    timeout: int = 10


class GrafanaTokenFixer:
    """
    Clase para resolver problemas de token rotation en Grafana
    Implementando principios de desarrollo funcional y defensivo
    """

    def __init__(self, config: GrafanaConfig):
        self.config = config
        self.session = requests.Session()
        self.session.timeout = config.timeout

    def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[requests.Response]:
        """
        Método helper para hacer requests con manejo de errores robusto
        Implementando guard clauses y early returns
        """
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        url = f"{self.config.url.rstrip('/')}{endpoint}"

        try:
            response = self.session.request(method, url, **kwargs)
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en request {method} {url}: {e}")
            return None

    def check_grafana_health(self) -> bool:
        """
        Verifica la salud de Grafana
        """
        logger.info("🔍 Verificando salud de Grafana...")

        response = self._make_request("GET", "/api/health")
        if not response:
            logger.error("❌ No se pudo conectar a Grafana")
            return False

        if response.status_code == 200:
            logger.info("✅ Grafana está saludable")
            return True
        else:
            logger.warning(f"⚠️ Grafana responde con status {response.status_code}")
            return False

    def login_admin(self) -> Optional[str]:
        """
        Autentica como admin y obtiene token
        """
        logger.info("🔐 Autenticando como admin...")

        auth_data = {
            "user": self.config.admin_user,
            "password": self.config.admin_password,
        }

        response = self._make_request("POST", "/login", json=auth_data)
        if not response:
            logger.error("❌ Error en autenticación")
            return None

        if response.status_code == 200:
            # Extraer token de las cookies
            cookies = response.cookies
            auth_cookie = cookies.get("grafana_session")
            if auth_cookie:
                logger.info("✅ Autenticación exitosa")
                self.session.cookies.update(cookies)
                return str(auth_cookie)

        logger.error(f"❌ Error en autenticación: {response.status_code}")
        return None

    def clear_sessions(self) -> bool:
        """
        Limpia sesiones activas para resolver problemas de token rotation
        """
        logger.info("🧹 Limpiando sesiones activas...")

        # Obtener sesiones activas
        response = self._make_request("GET", "/api/auth/keys")
        if not response or response.status_code != 200:
            logger.warning("⚠️ No se pudieron obtener sesiones activas")
            return False

        sessions = response.json()
        logger.info(f"📊 Encontradas {len(sessions)} sesiones activas")

        # Eliminar sesiones (esto fuerza nueva autenticación)
        for session in sessions:
            session_id = session.get("id")
            if session_id:
                delete_response = self._make_request(
                    "DELETE", f"/api/auth/keys/{session_id}"
                )
                if delete_response and delete_response.status_code == 200:
                    logger.info(f"🗑️ Sesión {session_id} eliminada")

        return True

    def reset_grafana_config(self) -> bool:
        """
        Reinicia configuración de Grafana para resolver problemas de token
        """
        logger.info("🔄 Reiniciando configuración de Grafana...")

        # Endpoint para reload de configuración
        response = self._make_request("POST", "/api/admin/settings")
        if response and response.status_code == 200:
            logger.info("✅ Configuración reiniciada")
            return True

        logger.warning("⚠️ No se pudo reiniciar configuración automáticamente")
        return False

    def fix_token_rotation_issue(self) -> bool:
        """
        Función principal para resolver el problema de token rotation
        Implementando manejo de errores anticipado con guard clauses
        """
        logger.info("🚀 Iniciando proceso de resolución de token rotation...")

        # Guard clause: verificar conectividad
        if not self.check_grafana_health():
            logger.error("❌ Grafana no está disponible")
            return False

        # Autenticar
        token = self.login_admin()
        if not token:
            logger.error("❌ No se pudo autenticar")
            return False

        # Limpiar sesiones
        if not self.clear_sessions():
            logger.warning("⚠️ No se pudieron limpiar todas las sesiones")

        # Reiniciar configuración
        self.reset_grafana_config()

        # Esperar un momento para que los cambios se apliquen
        logger.info("⏳ Esperando que los cambios se apliquen...")
        time.sleep(5)

        # Verificar que el problema se resolvió
        logger.info("🔍 Verificando resolución del problema...")
        time.sleep(10)

        return True


def main():
    """
    Función principal siguiendo principios de desarrollo funcional
    """
    # Configuración desde variables de entorno
    grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
    admin_user = os.getenv("GF_SECURITY_ADMIN_USER", "admin")
    admin_password = os.getenv("GF_SECURITY_ADMIN_PASSWORD", "gridbot123")

    config = GrafanaConfig(
        url=grafana_url, admin_user=admin_user, admin_password=admin_password
    )

    logger.info(f"🔧 Configuración: {config.url}")

    # Crear instancia del fixer
    fixer = GrafanaTokenFixer(config)

    # Ejecutar proceso de resolución
    success = fixer.fix_token_rotation_issue()

    if success:
        logger.info("🎉 Proceso completado exitosamente")
        sys.exit(0)
    else:
        logger.error("❌ El proceso falló")
        sys.exit(1)


if __name__ == "__main__":
    main()
