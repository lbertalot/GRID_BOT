"""Facade de breakers para el adaptador CEO (ADR-005 / Track F).

El overview espera `app.core.breakers_status.get_breakers_status()` con
`open_breakers` y `as_of`. Reusa la visibilidad compartida (misma fuente que
`GET /api/breakers/status`) para no inventar un segundo estado.

E5: digest desk / cycle worker / API deben leer la misma lista
``active_breakers`` vía ``get_shared_breakers()`` (store Redis compartido).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from app.core.breaker_visibility import get_breaker_visibility_snapshot
from app.core.circuit_breakers import get_shared_breakers

logger = logging.getLogger(__name__)


def get_active_breaker_names() -> List[str]:
    """Fuente única de breakers abiertos (API ↔ worker ↔ digest).

    Lee ``get_shared_breakers().get_all_breakers_status()`` tras refresh del
    store Redis/memory — la misma llamada que usa el trading cycle.
    """
    summary = get_shared_breakers().get_all_breakers_status()
    active = summary.get("active_breakers") or []
    return [str(name) for name in active]


def get_breakers_status() -> Dict[str, Any]:
    """Estado consolidado para CEO overview / desk digest (solo lectura)."""
    # Misma fuente que el cycle (active_breakers del store compartido).
    open_breakers = get_active_breaker_names()
    # Visibilidad adicional (emergency_stop, métricas) sin divergir any_open.
    snapshot = get_breaker_visibility_snapshot(get_shared_breakers())
    return {
        "open_breakers": open_breakers,
        "any_open": len(open_breakers) > 0,
        "emergency_stop": bool(snapshot.get("emergency_stop")),
        "as_of": snapshot.get("generated_at")
        or datetime.now(timezone.utc).isoformat(),
    }


def log_cycle_breakers_status(
    *,
    active_breakers: Optional[Sequence[str]] = None,
    newly_activated: Optional[Sequence[str]] = None,
) -> None:
    """Log honest del cycle: WARNING solo si hay breakers activos.

    Evita el falso positivo ``Circuit breakers activos: []`` (P0.7 / E5) que
    logueaba ``breakers_activated`` (delta del ciclo) en vez del estado shared.
    """
    active = list(active_breakers if active_breakers is not None else get_active_breaker_names())
    newly = list(newly_activated or [])
    if active:
        logger.warning(
            "[Cycle] Circuit breakers activos: %s (newly=%s)",
            active,
            newly,
        )
    else:
        logger.info(
            "[Cycle] Circuit breakers activos: [] (newly=%s)",
            newly,
        )


__all__ = [
    "get_active_breaker_names",
    "get_breakers_status",
    "log_cycle_breakers_status",
]
