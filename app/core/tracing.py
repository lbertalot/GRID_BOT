"""
observability-tracing-agent — Distributed tracing con OpenTelemetry para GridBot.

Configura tracing automático para:
- FastAPI (todas las rutas HTTP)
- SQLAlchemy (queries a PostgreSQL)
- Requests/httpx (llamadas salientes a Binance API)
- Tareas Celery (via middleware de tracing)

Backends soportados (configurados via env):
  OTEL_EXPORTER=none      → tracing habilitado en memoria pero sin exportación (default)
  OTEL_EXPORTER=console   → logs de spans a stdout (solo para debug, genera mucho ruido)
  OTEL_EXPORTER=jaeger    → Jaeger via OTLP/gRPC
  OTEL_EXPORTER=otlp      → OTLP HTTP/gRPC (Grafana Tempo, New Relic, etc.)

Variables de entorno:
  OTEL_SERVICE_NAME           → nombre del servicio (default: gridbot)
  OTEL_EXPORTER               → backend (none|console|jaeger|otlp), default: none
  OTEL_EXPORTER_OTLP_ENDPOINT → endpoint OTLP (default: http://localhost:4317)
  OTEL_SAMPLE_RATE            → fracción de trazas a muestrear (default: 1.0)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Nombre del servicio en las trazas
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "gridbot")
EXPORTER = os.getenv("OTEL_EXPORTER", "none").lower()
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SAMPLE_RATE = float(os.getenv("OTEL_SAMPLE_RATE", "1.0"))


def setup_tracing(app=None) -> bool:
    """
    Inicializa OpenTelemetry con el exportador configurado.

    Retorna True si el setup fue exitoso, False si las dependencias
    no están instaladas (las dependencias OTel son opcionales).

    Uso en main.py lifespan:
        from app.core.tracing import setup_tracing
        setup_tracing(app)
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME as OTEL_SVC_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except ImportError:
        logger.info(
            "[Tracing] opentelemetry-sdk no instalado. "
            "Para habilitar: pip install opentelemetry-sdk opentelemetry-instrumentation-fastapi "
            "opentelemetry-instrumentation-sqlalchemy opentelemetry-exporter-otlp. "
            "El bot funciona normalmente sin tracing."
        )
        return False

    resource = Resource.create({OTEL_SVC_NAME: SERVICE_NAME})
    sampler = TraceIdRatioBased(SAMPLE_RATE)
    provider = TracerProvider(resource=resource, sampler=sampler)

    # ── Exportador ───────────────────────────────────────────────────────────
    exporter = _build_exporter()
    if exporter is not None:
        try:
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                "[Tracing] Exportador configurado: %s → %s",
                EXPORTER,
                OTLP_ENDPOINT if EXPORTER != "console" else "stdout",
            )
        except Exception as exc:
            logger.warning(
                "[Tracing] No se pudo configurar exportador %s: %s", EXPORTER, exc
            )

    trace.set_tracer_provider(provider)

    # ── Auto-instrumentación de FastAPI ──────────────────────────────────────
    if app is not None:
        _instrument_fastapi(app)

    # ── Auto-instrumentación de SQLAlchemy ───────────────────────────────────
    _instrument_sqlalchemy()

    # ── Auto-instrumentación de requests (Binance HTTP calls) ─────────────────
    _instrument_requests()

    logger.info(
        "[Tracing] OpenTelemetry inicializado: service=%s exporter=%s sample_rate=%.2f",
        SERVICE_NAME,
        EXPORTER,
        SAMPLE_RATE,
    )
    return True


def _build_exporter() -> Optional[object]:
    """Construye el exportador de trazas según OTEL_EXPORTER."""
    if EXPORTER in ("none", "off", "disabled", ""):
        logger.info(
            "[Tracing] Exportador deshabilitado (OTEL_EXPORTER=%s).",
            EXPORTER or "unset",
        )
        return None

    if EXPORTER == "console":
        try:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            return ConsoleSpanExporter()
        except ImportError:
            return None

    if EXPORTER in ("otlp", "jaeger"):
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            return OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
        except ImportError:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                endpoint_http = OTLP_ENDPOINT.replace("4317", "4318")
                return OTLPSpanExporter(endpoint=f"{endpoint_http}/v1/traces")
            except ImportError:
                logger.warning(
                    "[Tracing] opentelemetry-exporter-otlp no instalado. "
                    "Instalar: pip install opentelemetry-exporter-otlp-proto-grpc"
                )
                return None

    logger.warning("[Tracing] Exportador desconocido: %s", EXPORTER)
    return None


def _instrument_fastapi(app) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/healthz,/metrics,/favicon.ico",
        )
        logger.debug("[Tracing] FastAPI instrumentado")
    except ImportError:
        logger.debug("[Tracing] opentelemetry-instrumentation-fastapi no instalado")


def _instrument_sqlalchemy() -> None:
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from app.db.session import engine

        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.debug("[Tracing] SQLAlchemy instrumentado")
    except Exception as exc:
        logger.debug("[Tracing] SQLAlchemy instrumentation no disponible: %s", exc)


def _instrument_requests() -> None:
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
        logger.debug("[Tracing] requests instrumentado")
    except ImportError:
        logger.debug("[Tracing] opentelemetry-instrumentation-requests no instalado")


def get_tracer(name: str = SERVICE_NAME):
    """
    Retorna un tracer de OpenTelemetry para crear spans manuales.

    Uso en servicios:
        from app.core.tracing import get_tracer
        tracer = get_tracer(__name__)

        with tracer.start_as_current_span("mi_operacion") as span:
            span.set_attribute("symbol", "BTCUSDT")
            ...
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return _NoOpTracer()


class _NoOpTracer:
    """Tracer vacío cuando OpenTelemetry no está instalado."""

    class _NoOpSpan:
        def set_attribute(self, *args, **kwargs):
            pass

        def set_status(self, *args, **kwargs):
            pass

        def record_exception(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def start_as_current_span(self, name, **kwargs):
        return self._NoOpSpan()

    def start_span(self, name, **kwargs):
        return self._NoOpSpan()
