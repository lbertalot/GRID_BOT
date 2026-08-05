"""Alertas ops cap / reserva proyectada — ADR-008 / blocker B20.

El ledger (`ops_ledger.summary`) solo calcula flags booleanos. Este módulo es el
emit path: publica gauges Prometheus y notifica Telegram en rising-edge
(False→True), reutilizando `send_telegram_alert` (sin stack nuevo).

Paper-safe: no toca órdenes, exchange ni flags live. Fallos de métrica/Telegram
nunca rompen el response HTTP del ledger.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

KIND_CAP = "cap_exceeded"
KIND_RESERVE = "reserve_exhausted_projection"

# Estado en proceso para edge-trigger (una notificación por transición).
_last_cap_exceeded: Optional[bool] = None
_last_reserve_exhausted: Optional[bool] = None


def reset_ops_cap_alert_state() -> None:
    """Resetea el estado de rising-edge (tests / reinicio limpio)."""
    global _last_cap_exceeded, _last_reserve_exhausted
    _last_cap_exceeded = None
    _last_reserve_exhausted = None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _telegram(message: str) -> bool:
    try:
        from app.services.telegram_alert import send_telegram_alert

        return bool(send_telegram_alert(message))
    except Exception as exc:  # pragma: no cover - defensa en profundidad
        logger.warning("Telegram ops-cap no enviado: %s", exc)
        return False


def _publish_gauges(*, cap_exceeded: bool, reserve_exhausted: bool) -> None:
    try:
        from app.core.metrics import (
            ops_monthly_cap_exceeded,
            ops_reserve_exhausted_projection,
        )

        ops_monthly_cap_exceeded.set(1 if cap_exceeded else 0)
        ops_reserve_exhausted_projection.set(1 if reserve_exhausted else 0)
    except Exception as exc:  # pragma: no cover
        logger.debug("No se pudieron publicar gauges ops-cap: %s", exc)


def _fire_counter(kind: str) -> None:
    try:
        from app.core.metrics import ops_cap_alerts_fired_total

        ops_cap_alerts_fired_total.labels(kind=kind).inc()
    except Exception as exc:  # pragma: no cover
        logger.debug("No se pudo incrementar counter ops-cap (%s): %s", kind, exc)


def emit_ops_cap_alerts(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Publica métricas y, en rising-edge, alerta Telegram.

    Returns:
        Dict con flags actuales y si se disparó cada alerta en esta llamada.
    """
    global _last_cap_exceeded, _last_reserve_exhausted

    cap_exceeded = _as_bool(summary.get("cap_exceeded", False))
    reserve_exhausted = _as_bool(summary.get("reserve_exhausted_projection", False))

    _publish_gauges(
        cap_exceeded=cap_exceeded, reserve_exhausted=reserve_exhausted
    )

    fired_cap = False
    fired_reserve = False

    if cap_exceeded and _last_cap_exceeded is not True:
        fired_cap = True
        _fire_counter(KIND_CAP)
        burn = summary.get("ops_burn_mtd", "?")
        cap = summary.get("monthly_cap", "?")
        month = summary.get("month", "?")
        _telegram(
            "🚨 OPS CAP EXCEDIDO (ADR-008)\n"
            f"Mes {month}: burn MTD {burn} USD > cap {cap} USD.\n"
            "Revisar /api/ops/summary — paper/ops only, no es señal de trading."
        )

    if reserve_exhausted and _last_reserve_exhausted is not True:
        fired_reserve = True
        _fire_counter(KIND_RESERVE)
        projected = summary.get("projected_annual_burn", "?")
        reserve = summary.get("ops_reserve_total", "?")
        _telegram(
            "🚨 OPS RESERVA PROYECTADA AGOTADA (ADR-008 #4)\n"
            f"Proyección anual {projected} USD > reserva {reserve} USD.\n"
            "Revisar /api/ops/summary — paper/ops only, no es señal de trading."
        )

    _last_cap_exceeded = cap_exceeded
    _last_reserve_exhausted = reserve_exhausted

    return {
        "cap_exceeded": cap_exceeded,
        "reserve_exhausted_projection": reserve_exhausted,
        "fired_cap_exceeded": fired_cap,
        "fired_reserve_exhausted_projection": fired_reserve,
    }
