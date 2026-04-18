"""
Middleware de distributed tracing para tareas Celery.

Propaga el contexto de trace de FastAPI → Celery worker,
de modo que el span de la tarea aparece como hijo del
span del request HTTP que la encoló.

Activación automática al importar este módulo.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def install_celery_tracing() -> bool:
    """
    Instala los signals de Celery que propagan el contexto OTel.

    Retorna True si la instalación fue exitosa, False si las
    dependencias no están disponibles.
    """
    try:
        from opentelemetry import trace, context
        from opentelemetry.propagate import inject, extract
        from celery.signals import (
            task_prerun,
            task_postrun,
            task_failure,
        )
    except ImportError:
        logger.debug("[CeleryTracing] opentelemetry o celery no disponibles — tracing desactivado")
        return False

    _active_spans: dict[str, object] = {}

    @task_prerun.connect
    def _on_task_prerun(task_id: str, task, *args, **kwargs):
        """Inicia un nuevo span por cada tarea Celery."""
        try:
            tracer = trace.get_tracer("celery")
            # Extraer contexto propagado desde el producer (si existe)
            headers = getattr(task.request, "headers", {}) or {}
            ctx = extract(headers)
            token = context.attach(ctx)
            span = tracer.start_span(
                f"celery.{task.name}",
                context=ctx,
                attributes={
                    "celery.task_id": task_id,
                    "celery.task_name": task.name,
                    "celery.routing_key": getattr(task.request, "delivery_info", {}).get("routing_key", ""),
                },
            )
            _active_spans[task_id] = (span, token)
        except Exception as exc:
            logger.debug("[CeleryTracing] Error en prerun: %s", exc)

    @task_postrun.connect
    def _on_task_postrun(task_id: str, *args, **kwargs):
        """Finaliza el span al completar la tarea."""
        _finish_span(task_id, success=True)

    @task_failure.connect
    def _on_task_failure(task_id: str, exception: Exception, *args, **kwargs):
        """Registra el error y finaliza el span en caso de fallo."""
        entry = _active_spans.get(task_id)
        if entry:
            span, _ = entry
            try:
                from opentelemetry.trace import StatusCode
                span.set_status(StatusCode.ERROR, str(exception))
                span.record_exception(exception)
            except Exception:
                pass
        _finish_span(task_id, success=False)

    def _finish_span(task_id: str, success: bool) -> None:
        entry = _active_spans.pop(task_id, None)
        if entry is None:
            return
        span, token = entry
        try:
            span.end()
        except Exception:
            pass
        try:
            from opentelemetry import context as ctx_api
            ctx_api.detach(token)
        except Exception:
            pass

    logger.info("[CeleryTracing] Signals de tracing instalados en Celery")
    return True


def inject_trace_headers() -> dict:
    """
    Retorna un dict con los headers W3C TraceContext / Baggage para
    propagar el span actual a workers Celery.

    Uso al encolar una tarea manualmente:
        headers = inject_trace_headers()
        mi_tarea.apply_async(headers=headers)
    """
    try:
        from opentelemetry.propagate import inject as otel_inject
        carrier: dict = {}
        otel_inject(carrier)
        return carrier
    except ImportError:
        return {}
