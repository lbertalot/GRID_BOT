"""
Decorador @traced para añadir spans OpenTelemetry a funciones críticas del bot.

Uso:
    from app.core.trace_decorator import traced

    @traced("trading.execute_order")
    async def execute_order(symbol: str, side: str, qty: Decimal):
        ...

    @traced("risk.calculate_var", attributes={"model": "historical"})
    def calculate_var(returns: list[float]) -> float:
        ...

Si OpenTelemetry no está instalado, el decorador es transparente (no-op).
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def traced(
    span_name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Decorador que envuelve una función en un span OTel.

    Args:
        span_name: Nombre del span. Si None, usa <module>.<funcname>.
        attributes: Atributos adicionales a agregar al span.
    """

    def decorator(fn: Callable) -> Callable:
        name = span_name or f"{fn.__module__}.{fn.__qualname__}"
        extra_attrs = attributes or {}

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                tracer = _get_tracer()
                with tracer.start_as_current_span(name) as span:
                    _set_attributes(span, extra_attrs)
                    try:
                        return await fn(*args, **kwargs)
                    except Exception as exc:
                        _record_error(span, exc)
                        raise

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                tracer = _get_tracer()
                with tracer.start_as_current_span(name) as span:
                    _set_attributes(span, extra_attrs)
                    try:
                        return fn(*args, **kwargs)
                    except Exception as exc:
                        _record_error(span, exc)
                        raise

            return sync_wrapper

    return decorator


def _get_tracer():
    from app.core.tracing import get_tracer

    return get_tracer("gridbot")


def _set_attributes(span, attrs: dict) -> None:
    try:
        for k, v in attrs.items():
            span.set_attribute(k, str(v))
    except Exception:
        pass


def _record_error(span, exc: Exception) -> None:
    try:
        from opentelemetry.trace import StatusCode

        span.set_status(StatusCode.ERROR, str(exc))
        span.record_exception(exc)
    except Exception:
        pass
