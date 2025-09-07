from __future__ import annotations

from typing import Callable, Awaitable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class IntegrityGuardMiddleware(BaseHTTPMiddleware):
    """
    Middleware que bloquea operaciones de escritura cuando hay circuit breakers activos.

    Usa request.app.state.breakers (inyectado desde app.main) para consultar estado.
    Bloquea métodos: POST/PUT/DELETE en rutas sensibles (prefijo /api/trade, /api/strategies).
    """

    def __init__(self, app, protected_prefixes: list[str] | None = None) -> None:
        super().__init__(app)
        self._protected_prefixes = protected_prefixes or ["/api/trade", "/api/strategies"]

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        method = request.method.upper()
        path = request.url.path

        # Permitir lectura y rutas públicas
        if method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        if path.startswith("/breakers/summary") or path.startswith("/api/reconciliation/summary"):
            return await call_next(request)

        if any(path.startswith(p) for p in self._protected_prefixes):
            breakers = getattr(request.app.state, "breakers", None)
            try:
                if breakers:
                    summary = breakers.get_all_breakers_status()
                    if summary.get("total_active", 0) > 0 or summary.get("critical_mode"):
                        return JSONResponse(
                            status_code=503,
                            content={
                                "status": "blocked",
                                "reason": "circuit_breaker_active",
                                "breakers": summary,
                            },
                        )
            except Exception:
                # En caso de error, continuar para no derribar la API
                pass

        return await call_next(request)


