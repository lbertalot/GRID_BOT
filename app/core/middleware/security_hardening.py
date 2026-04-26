"""
api-security-hardening-agent — Middleware de seguridad para GridBot.

Provee tres capas de protección:

1. SecurityHeadersMiddleware
   Añade headers HTTP de seguridad en todas las respuestas:
   - Strict-Transport-Security (HSTS)
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: DENY
   - Content-Security-Policy
   - Referrer-Policy
   - Permissions-Policy
   - X-Request-ID (para correlación de logs)

2. RateLimitMiddleware
   Rate limiting en memoria por IP (sliding window).
   Configurable vía variables de entorno:
     RATE_LIMIT_REQUESTS=100   (requests por ventana)
     RATE_LIMIT_WINDOW=60      (tamaño de ventana en segundos)
   Retorna 429 con Retry-After cuando se supera el límite.

3. InputSanitizationMiddleware
   Rechaza requests con caracteres de inyección en path y query params.
   Lista de patrones: SQL injection básico, path traversal, command injection.

Activación en main.py:
    from app.core.middleware.security_hardening import (
        SecurityHeadersMiddleware,
        RateLimitMiddleware,
        InputSanitizationMiddleware,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(InputSanitizationMiddleware)
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from collections import defaultdict, deque
from typing import Callable, Dict, Deque

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# ── Configuración via env ─────────────────────────────────────────────────────
_RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
_RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # segundos

# Rutas exentas del rate limiting (métricas internas, healthchecks)
_RATE_LIMIT_EXEMPT_PATHS = frozenset(
    {
        "/healthz",
        "/health",
        "/metrics",
        "/favicon.ico",
    }
)

# ── Patrones de inyección a rechazar en path/query ───────────────────────────
_INJECTION_PATTERNS = re.compile(
    r"(\.\./|\.\.\\|%2e%2e|%252e|"  # path traversal
    r"union\s+select|drop\s+table|insert\s+into|"  # SQL injection
    r"<script|javascript:|vbscript:|data:text/html|"  # XSS
    r";\s*(cat|ls|wget|curl|bash|sh)\s+|"  # command injection
    r"\x00|\x0d\x0a)",  # null byte / CRLF
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Security Headers Middleware
# ─────────────────────────────────────────────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Añade headers de seguridad estándar a todas las respuestas HTTP."""

    _HEADERS: Dict[str, str] = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'"
        ),
        # Eliminar header que revela la tecnología del servidor
        "Server": "gridbot",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        # Propagar request ID al scope para que otros middlewares lo usen
        request.state.request_id = request_id

        response = await call_next(request)

        for header, value in self._HEADERS.items():
            response.headers[header] = value
        response.headers["X-Request-ID"] = request_id

        return response


# ─────────────────────────────────────────────────────────────────────────────
# 2. Rate Limit Middleware (sliding window, en memoria)
# ─────────────────────────────────────────────────────────────────────────────


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting por IP usando sliding window counter en memoria.

    Para producción con múltiples workers considera usar Redis
    (reemplazar `_windows` por un counter en Redis con EXPIRE).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        # IP → deque de timestamps de requests recientes
        self._windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._requests = _RATE_LIMIT_REQUESTS
        self._window = _RATE_LIMIT_WINDOW

    def _get_client_ip(self, request: Request) -> str:
        """Extrae la IP real respetando X-Forwarded-For (Heroku/proxies)."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_allowed(self, ip: str) -> tuple[bool, int]:
        """
        Devuelve (permitido, tiempo_de_espera_en_segundos).
        Tiempo de espera = 0 si está permitido.
        """
        now = time.monotonic()
        window = self._windows[ip]

        # Descartar timestamps fuera de la ventana deslizante
        cutoff = now - self._window
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= self._requests:
            # Tiempo hasta que el request más antiguo salga de la ventana
            retry_after = int(self._window - (now - window[0])) + 1
            return False, retry_after

        window.append(now)
        return True, 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Rutas exentas
        if path in _RATE_LIMIT_EXEMPT_PATHS:
            return await call_next(request)

        ip = self._get_client_ip(request)
        allowed, retry_after = self._is_allowed(ip)

        if not allowed:
            logger.warning(
                "[RateLimit] IP %s superó el límite (%d req/%ds) en %s",
                ip,
                self._requests,
                self._window,
                path,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas solicitudes. Intenta más tarde."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self._requests),
                    "X-RateLimit-Window": str(self._window),
                },
            )

        response = await call_next(request)
        # Informar al cliente cuántos requests le quedan
        remaining = max(0, self._requests - len(self._windows[ip]))
        response.headers["X-RateLimit-Limit"] = str(self._requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(self._window)
        return response


# ─────────────────────────────────────────────────────────────────────────────
# 3. Input Sanitization Middleware
# ─────────────────────────────────────────────────────────────────────────────


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Rechaza requests con patrones de inyección en path y query string.

    Solo inspecciona la URL/query — el body se valida con Pydantic en cada
    endpoint. Este middleware actúa como primera línea de defensa.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Inspeccionar path
        raw_path = str(request.url.path)
        query = str(request.url.query)
        target = raw_path + "?" + query if query else raw_path

        if _INJECTION_PATTERNS.search(target):
            logger.warning(
                "[InputSanitization] Request bloqueado: IP=%s método=%s url=%s",
                request.client.host if request.client else "unknown",
                request.method,
                target[:200],
            )
            return JSONResponse(
                status_code=400,
                content={"detail": "Input inválido detectado."},
            )

        return await call_next(request)
