"""Facade de breakers para el adaptador CEO (ADR-005 / Track F).

El overview espera `app.core.breakers_status.get_breakers_status()` con
`open_breakers` y `as_of`. Reusa la visibilidad compartida (misma fuente que
`GET /api/breakers/status`) para no inventar un segundo estado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.breaker_visibility import get_breaker_visibility_snapshot
from app.core.circuit_breakers import get_shared_breakers


def get_breakers_status() -> Dict[str, Any]:
    """Estado consolidado para CEO overview (solo lectura)."""
    snapshot = get_breaker_visibility_snapshot(get_shared_breakers())
    open_breakers: List[str] = [
        str(item.get("name") or item.get("breaker") or item)
        for item in (snapshot.get("breakers") or [])
        if (item.get("state") if isinstance(item, dict) else None) == "open"
    ]
    if not open_breakers and snapshot.get("any_open"):
        # Fallback si el snapshot marca any_open sin detalle de nombres.
        open_breakers = ["any_open"]
    return {
        "open_breakers": open_breakers,
        "any_open": bool(snapshot.get("any_open")),
        "emergency_stop": bool(snapshot.get("emergency_stop")),
        "as_of": snapshot.get("generated_at")
        or datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["get_breakers_status"]
