"""Política paper-safe del estado operativo de ``system_integrity``.

No autoriza órdenes: devuelve decisiones deterministas para que API, workers y
ejecutores apliquen la misma guarda. Cualquier estado desconocido falla cerrado.
"""
from __future__ import annotations

from enum import StrEnum
from decimal import Decimal
from typing import Any, Mapping


class SystemIntegrityState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    REDUCE_ONLY = "REDUCE_ONLY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class SystemIntegrityOrderBlocked(ValueError):
    """Una orden no puede cruzar el límite de integridad operativo."""


def operational_state(record: Any) -> SystemIntegrityState:
    """Normaliza legacy: breaker activo sin enum equivale a REDUCE_ONLY."""
    raw = getattr(record, "operational_state", None)
    if raw is None and isinstance(record, dict):
        raw = record.get("operational_state")
    active = getattr(record, "active", False)
    if isinstance(record, dict):
        active = record.get("active", active)
    if raw is None:
        return SystemIntegrityState.REDUCE_ONLY if active else SystemIntegrityState.CLOSED
    try:
        return SystemIntegrityState(str(raw).upper())
    except ValueError as exc:
        raise ValueError("system_integrity operational_state inválido") from exc


def system_integrity_record_from_breaker_summary(
    summary: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Extrae el record SI y rechaza snapshots incompletos con SI marcado activo."""
    details = summary.get("breakers")
    record = details.get("system_integrity") if isinstance(details, Mapping) else None
    active_breakers = summary.get("active_breakers") or ()
    listed_active = "system_integrity" in active_breakers
    if record is None:
        if listed_active:
            raise SystemIntegrityOrderBlocked(
                "system_integrity activo sin estado operativo verificable"
            )
        return {"active": False}
    if not isinstance(record, Mapping):
        raise SystemIntegrityOrderBlocked("system_integrity record inválido")
    if listed_active and not record.get("active", False):
        raise SystemIntegrityOrderBlocked("system_integrity inconsistente")
    return record


def assert_system_integrity_execution_allowed(
    *,
    record: Mapping[str, Any],
    side: str,
    reduce_only: bool,
    paper_only: bool,
) -> SystemIntegrityState:
    """Aplica estado SI antes de una orden; REDUCE_ONLY solo existe en PAPER.

    El contrato PAPER puede reservar y asentar una salida marcada reduce-only en
    el ledger. Nunca convierte esa autorización en una orden autenticada real.
    """
    state = operational_state(record)
    active = bool(record.get("active", False))
    if active and state is SystemIntegrityState.CLOSED:
        raise SystemIntegrityOrderBlocked("system_integrity activo inconsistente")
    try:
        from app.core.metrics import reduce_only_exit_checks_total, reduce_only_mode_active

        reduce_only_mode_active.set(int(state is SystemIntegrityState.REDUCE_ONLY))
    except Exception:
        pass
    if state is SystemIntegrityState.CLOSED:
        return state
    if state is not SystemIntegrityState.REDUCE_ONLY:
        raise SystemIntegrityOrderBlocked(f"system_integrity={state.value}")
    if not allows_order(state=state, side=side, reduce_only=reduce_only):
        try:
            reduce_only_exit_checks_total.labels(
                outcome="blocked", reason="not_reduce_sell"
            ).inc()
        except Exception:
            pass
        raise SystemIntegrityOrderBlocked(
            "system_integrity=REDUCE_ONLY requiere SELL marcado reduce_only"
        )
    if paper_only is not True:
        try:
            reduce_only_exit_checks_total.labels(
                outcome="blocked", reason="real_executor"
            ).inc()
        except Exception:
            pass
        raise SystemIntegrityOrderBlocked(
            "system_integrity=REDUCE_ONLY es un contrato paper-only"
        )
    try:
        reduce_only_exit_checks_total.labels(outcome="allowed", reason="paper").inc()
    except Exception:
        pass
    return state


def allows_order(*, state: SystemIntegrityState, side: str, reduce_only: bool) -> bool:
    """Autoriza solo SELL marcado reduce-only durante la contención."""
    normalized_side = str(side).upper()
    if state is SystemIntegrityState.CLOSED:
        return True
    return (
        state is SystemIntegrityState.REDUCE_ONLY
        and normalized_side == "SELL"
        and reduce_only is True
    )


def expected_reduce_only_pnl(
    *, quantity: Decimal, mark: Decimal, cost_basis: Decimal, sell_cost_bps: Decimal
) -> Decimal:
    """PnL esperado luego de costes de salida; argumentos monetarios Decimal."""
    if quantity <= 0 or mark <= 0 or cost_basis < 0 or sell_cost_bps < 0:
        raise ValueError("parámetros reduce-only inválidos")
    proceeds = quantity * mark
    return proceeds - proceeds * sell_cost_bps / Decimal("10000") - cost_basis


def eligible_reduce_only_quantity(
    *, quantity: Decimal, expected_net_pnl: Decimal, min_net_pnl: Decimal
) -> Decimal:
    """Retorna la cantidad entera elegible; nunca autoriza PnL bajo el umbral."""
    return quantity if quantity > 0 and expected_net_pnl >= min_net_pnl else Decimal("0")
