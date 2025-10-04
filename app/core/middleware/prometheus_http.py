from time import perf_counter
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Histogram, Counter


http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path", "status"],
    buckets=(0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5)
)

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"]
)


class PrometheusHTTPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        start = perf_counter()
        response = await call_next(request)
        duration = perf_counter() - start
        method = request.method
        # Normalizar path usando plantilla de ruta si está disponible
        route = getattr(request.scope.get("route"), "path", request.url.path)
        path = route
        status = str(response.status_code)
        http_request_duration_seconds.labels(method=method, path=path, status=status).observe(duration)
        http_requests_total.labels(method=method, path=path, status=status).inc()
        return response



