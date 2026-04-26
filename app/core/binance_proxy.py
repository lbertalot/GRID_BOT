"""
Helper para proxy de Binance.

Soporta dos variables de entorno (primera que tenga valor gana):
  1. QUOTAGUARDSHIELD_URL  – legacy (QuotaGuard Shield en Heroku)
  2. BINANCE_PROXY_URL     – genérica (cualquier proxy HTTPS/SOCKS5)

Si ninguna está definida, el tráfico a Binance sale directo (sin proxy).
Esto funciona correctamente desde Heroku EU, donde no hay bloqueo 451.

Solo tráfico hacia Binance debe usar proxy; Redis, Postgres, etc. no.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_PROXY_ENV_VARS = ("QUOTAGUARDSHIELD_URL", "BINANCE_PROXY_URL")


def _resolve_proxy_url() -> Optional[str]:
    """Resuelve la URL de proxy desde las variables de entorno soportadas."""
    for var in _PROXY_ENV_VARS:
        url = os.getenv(var, "").strip()
        if url:
            return url
    return None


def get_binance_proxies() -> Optional[dict[str, str]]:
    """
    Retorna dict de proxies para requests/Client si existe alguna URL de proxy.
    Uso: requests.get(url, proxies=proxies) o Client(..., requests_params={"proxies": proxies}).
    """
    url = _resolve_proxy_url()
    if not url:
        return None
    return {"http": url, "https": url}


def get_binance_proxy_url() -> Optional[str]:
    """
    Retorna la URL del proxy para aiohttp (proxy= en ClientSession.post/put/ws_connect).
    """
    return _resolve_proxy_url()


def log_proxy_status() -> None:
    """Loguea una sola vez el estado del proxy al arranque."""
    url = _resolve_proxy_url()
    if url:
        # No loguear la URL completa (contiene credenciales)
        masked = url.split("@")[-1] if "@" in url else url[:30]
        logger.warning(f"Proxy activo para Binance: ...@{masked}")
    else:
        logger.info(
            "Sin proxy para Binance — conexión directa desde la región del dyno"
        )
