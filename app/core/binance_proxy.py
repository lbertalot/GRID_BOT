"""
Helper para proxy de Binance (QuotaGuard Shield en Heroku).
Solo tráfico hacia Binance debe usar proxy; Redis, Postgres, etc. no.
"""
from __future__ import annotations

import os
from typing import Optional


def get_binance_proxies() -> Optional[dict[str, str]]:
    """
    Retorna dict de proxies para requests/Client si existe QUOTAGUARDSHIELD_URL.
    Uso: requests.get(url, proxies=proxies) o Client(..., requests_params={"proxies": proxies}).
    """
    url = os.getenv("QUOTAGUARDSHIELD_URL", "").strip()
    if not url:
        return None
    return {"http": url, "https": url}


def get_binance_proxy_url() -> Optional[str]:
    """
    Retorna la URL del proxy para aiohttp (proxy= en ClientSession.post/put/ws_connect).
    """
    return os.getenv("QUOTAGUARDSHIELD_URL", "").strip() or None
