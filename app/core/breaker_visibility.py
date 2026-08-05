"""Snapshot consolidado de circuit breakers para operadores y dashboards.

Slice S7: la información de breakers estaba repartida entre `CircuitBreakers`
(estado), `AutoCircuitBreaker` (umbrales) y el modo de trading (emergency stop).
Este módulo la unifica en un único payload de solo lectura.

No cambia el comportamiento de ningún breaker: solo observa y publica.
No incluye secretos: el payload se arma con nombres, estados y umbrales.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.circuit_breakers import CircuitBreakers, get_shared_breakers

BREAKER_STATE_CLOSED = "closed"
BREAKER_STATE_OPEN = "open"
BREAKER_STATE_HALF_OPEN = "half_open"

# Umbral que dispara cada breaker en `AutoCircuitBreaker`. Se usa como fallback
# si el módulo no puede importarse (p. ej. sin DB configurada).
_THRESHOLD_BY_BREAKER: Dict[str, Tuple[str, float]] = {
    "balance_discrepancy": ("max_daily_loss_pct", 0.05),
    "operation_failure_rate": ("max_total_loss_pct", 0.10),
    "system_integrity": ("max_consecutive_losses", 5),
    "critical_mode": ("critical_loss_pct", 0.20),
}


def _env_emergency_stop() -> bool:
    """Lee el emergency stop del snapshot de modo de trading (Track S1)."""
    try:
        from app.core.trading_mode import get_trading_mode_snapshot

        return bool(get_trading_mode_snapshot().get("emergency_stop", False))
    except Exception:
        return False


def _live_thresholds() -> Dict[str, float]:
    """Umbrales vigentes en AutoCircuitBreaker, para que el payload no drifte."""
    try:
        from app.core.auto_circuit_breaker import auto_circuit_breaker

        return dict(auto_circuit_breaker.thresholds)
    except Exception:
        return {}


def _threshold_for(
    breaker_name: str, live: Dict[str, float]
) -> Tuple[Optional[str], Optional[float]]:
    metric, fallback = _THRESHOLD_BY_BREAKER.get(breaker_name, (None, None))
    if metric is None:
        return None, None
    return metric, float(live.get(metric, fallback))


def _cooldown_remaining_s(breakers: CircuitBreakers, name: str, now: float) -> float:
    last = breakers.get_last_activation_ts(name)
    if last <= 0:
        return 0.0
    remaining = breakers.get_cooldown_seconds() - (now - last)
    return round(remaining, 3) if remaining > 0 else 0.0


def _publish_metrics(
    breakers_payload: List[Dict[str, Any]], snapshot: Dict[str, Any]
) -> None:
    """Refleja el snapshot en Prometheus. Nunca debe romper la respuesta HTTP."""
    try:
        from app.core.metrics import (
            active_breakers_total,
            breaker_any_open,
            breaker_state,
            emergency_stop_active,
        )

        for breaker in breakers_payload:
            breaker_state.labels(type=breaker["name"]).set(
                1 if breaker["state"] == BREAKER_STATE_OPEN else 0
            )
        active_breakers_total.set(snapshot["open_count"])
        breaker_any_open.set(1 if snapshot["any_open"] else 0)
        emergency_stop_active.set(1 if snapshot["emergency_stop"] else 0)
    except Exception:
        pass


def get_breaker_visibility_snapshot(
    breakers: Optional[CircuitBreakers] = None,
) -> Dict[str, Any]:
    """Estado consolidado de todos los circuit breakers conocidos.

    Estados reportados:
      - `open`: el breaker está activo y frena la operatoria.
      - `half_open`: cerrado pero dentro de la ventana de cooldown, es decir
        todavía no puede volver a dispararse.
      - `closed`: cerrado y habilitado para dispararse.
    """
    breakers = breakers if breakers is not None else get_shared_breakers()
    now = time.time()
    live_thresholds = _live_thresholds()

    payload: List[Dict[str, Any]] = []
    for name, state in breakers.breakers.items():
        is_open = bool(state.get("active"))
        cooldown_remaining = _cooldown_remaining_s(breakers, name, now)
        if is_open:
            breaker_state_label = BREAKER_STATE_OPEN
        elif cooldown_remaining > 0:
            breaker_state_label = BREAKER_STATE_HALF_OPEN
        else:
            breaker_state_label = BREAKER_STATE_CLOSED

        threshold_metric, threshold = _threshold_for(name, live_thresholds)
        payload.append(
            {
                "name": name,
                "state": breaker_state_label,
                "reason": state.get("reason"),
                "opened_at": state.get("activated_at"),
                "cooldown_remaining_s": cooldown_remaining,
                "failure_count": breakers.get_activation_count(name),
                "threshold": threshold,
                "threshold_metric": threshold_metric,
            }
        )

    open_count = sum(1 for b in payload if b["state"] == BREAKER_STATE_OPEN)
    snapshot: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "any_open": open_count > 0,
        "open_count": open_count,
        "emergency_stop": _env_emergency_stop() or breakers.is_critical_mode_active(),
        "cooldown_seconds": breakers.get_cooldown_seconds(),
        "breakers": payload,
    }

    _publish_metrics(payload, snapshot)
    return snapshot
