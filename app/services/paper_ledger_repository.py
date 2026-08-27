"""Operaciones transaccionales del ledger PAPER para reservas reduce-only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.metrics import paper_ledger_transactions_total
from app.models.paper_ledger import (
    PaperLedgerCycle,
    PaperLedgerFill,
    PaperLedgerIntent,
    PaperLedgerReservation,
)


class PaperLedgerReservationError(ValueError):
    pass


class PaperLedgerSettlementError(ValueError):
    pass


@dataclass(frozen=True)
class PaperLedgerFillAllocation:
    """Fill PAPER ya simulado; este objeto no envía órdenes a ningún venue."""

    cycle_id: str
    quantity: Decimal


def _decimal(value: Decimal, *, field_name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise PaperLedgerReservationError(
            f"{field_name} debe ser Decimal, no {type(value).__name__}"
        )
    if not isinstance(value, Decimal):
        raise PaperLedgerReservationError(f"{field_name} debe ser Decimal")
    return value.normalize()


def _normalized_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise PaperLedgerReservationError("symbol inválido")
    return normalized


def _validate_client_order_id(client_order_id: str) -> str:
    normalized = str(client_order_id).strip()
    if not normalized:
        raise PaperLedgerReservationError("client_order_id inválido")
    return normalized


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def reserve_reduce_only(
    db: Session, *, symbol: str, allocations: dict[str, Decimal], client_order_id: str, ttl_seconds: int = 300
) -> str:
    """Reserva inventario PAPER bajo locks; el llamador controla commit/rollback."""
    normalized_symbol = _normalized_symbol(symbol)
    normalized_client_order_id = _validate_client_order_id(client_order_id)
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or ttl_seconds <= 0:
        raise PaperLedgerReservationError("ttl_seconds debe ser un entero positivo")
    if not allocations:
        raise PaperLedgerReservationError("allocations inválidas")
    normalized_allocations = {
        cycle_id: _decimal(quantity, field_name=f"allocation[{cycle_id}]")
        for cycle_id, quantity in allocations.items()
    }
    if any(not cycle_id or quantity <= 0 for cycle_id, quantity in normalized_allocations.items()):
        raise PaperLedgerReservationError("allocations inválidas")

    existing = (
        db.query(PaperLedgerIntent)
        .filter_by(client_order_id=normalized_client_order_id)
        .one_or_none()
    )
    if existing:
        return existing.intent_id
    ids = sorted(normalized_allocations)
    cycles = (
        db.query(PaperLedgerCycle).filter(PaperLedgerCycle.cycle_id.in_(ids))
        .with_for_update().all()
    )
    by_id = {cycle.cycle_id: cycle for cycle in cycles}
    if set(by_id) != set(ids):
        raise PaperLedgerReservationError("cycle_id desconocido")
    now = datetime.now(timezone.utc)
    active_reservations = (
        db.query(PaperLedgerReservation)
        .join(PaperLedgerIntent)
        .filter(
            PaperLedgerReservation.cycle_id.in_(ids),
            PaperLedgerIntent.state == "RESERVED",
            PaperLedgerReservation.expires_at > now,
        )
        .all()
    )
    reserved_by_cycle: dict[str, Decimal] = {}
    for reservation in active_reservations:
        reserved_by_cycle[reservation.cycle_id] = (
            reserved_by_cycle.get(reservation.cycle_id, Decimal("0"))
            + Decimal(str(reservation.quantity))
        )
    for cycle_id, qty in normalized_allocations.items():
        cycle = by_id[cycle_id]
        available = Decimal(str(cycle.open_quantity)) - reserved_by_cycle.get(
            cycle_id, Decimal("0")
        )
        if (
            cycle.symbol != normalized_symbol
            or cycle.closed_at is not None
            or available < qty
        ):
            raise PaperLedgerReservationError("inventario no reducible")
    intent_id = f"reduce-{uuid4().hex}"
    db.add(
        PaperLedgerIntent(
            intent_id=intent_id,
            client_order_id=normalized_client_order_id,
            symbol=normalized_symbol,
            side="SELL",
            state="RESERVED",
            created_at=now,
        )
    )
    for cycle_id, qty in normalized_allocations.items():
        db.add(PaperLedgerReservation(intent_id=intent_id, cycle_id=cycle_id, quantity=qty, expires_at=now + timedelta(seconds=ttl_seconds)))
    db.flush()
    paper_ledger_transactions_total.labels(operation="reserve", outcome="success").inc()
    return intent_id


def settle_reduce_only(
    db: Session,
    *,
    intent_id: str,
    allocations: tuple[PaperLedgerFillAllocation, ...],
    price: Decimal,
    executed_at: datetime | None = None,
) -> tuple[str, ...]:
    """Asienta fills PAPER completos contra una reserva vigente, de forma atómica."""
    if not allocations:
        raise PaperLedgerSettlementError("allocations inválidas")
    if isinstance(price, bool) or isinstance(price, float) or not isinstance(price, Decimal):
        raise PaperLedgerSettlementError("price debe ser Decimal")
    normalized_price = price.normalize()
    if normalized_price <= 0:
        raise PaperLedgerSettlementError("price debe ser positivo")
    if not intent_id:
        raise PaperLedgerSettlementError("intent_id inválido")

    intent = (
        db.query(PaperLedgerIntent)
        .filter_by(intent_id=intent_id)
        .with_for_update()
        .one_or_none()
    )
    if intent is None or intent.side != "SELL":
        raise PaperLedgerSettlementError("intent reduce-only desconocido")
    if intent.state == "FILLED":
        return tuple(
            row.fill_id
            for row in db.query(PaperLedgerFill)
            .filter_by(intent_id=intent_id)
            .order_by(PaperLedgerFill.cycle_id)
            .all()
        )
    if intent.state != "RESERVED":
        raise PaperLedgerSettlementError("intent no reservada")

    reservations = (
        db.query(PaperLedgerReservation)
        .filter_by(intent_id=intent_id)
        .with_for_update()
        .all()
    )
    now = datetime.now(timezone.utc)
    if not reservations or any(
        _as_utc(reservation.expires_at) <= now for reservation in reservations
    ):
        raise PaperLedgerSettlementError("reserva vencida o ausente")

    requested = {}
    for allocation in allocations:
        if (
            not allocation.cycle_id
            or isinstance(allocation.quantity, bool)
            or isinstance(allocation.quantity, float)
            or not isinstance(allocation.quantity, Decimal)
            or allocation.quantity <= 0
        ):
            raise PaperLedgerSettlementError("allocations inválidas")
        if allocation.cycle_id in requested:
            raise PaperLedgerSettlementError("cycle_id duplicado")
        requested[allocation.cycle_id] = allocation.quantity.normalize()
    reserved = {
        reservation.cycle_id: Decimal(str(reservation.quantity))
        for reservation in reservations
    }
    if requested != reserved:
        raise PaperLedgerSettlementError("fill debe liquidar exactamente la reserva")

    cycles = (
        db.query(PaperLedgerCycle)
        .filter(PaperLedgerCycle.cycle_id.in_(sorted(reserved)))
        .with_for_update()
        .all()
    )
    by_id = {cycle.cycle_id: cycle for cycle in cycles}
    if set(by_id) != set(reserved):
        raise PaperLedgerSettlementError("cycle_id desconocido")
    moment = _as_utc(executed_at) if executed_at else now
    fill_ids = []
    for cycle_id in sorted(reserved):
        cycle = by_id[cycle_id]
        quantity = reserved[cycle_id]
        if cycle.closed_at is not None or Decimal(str(cycle.open_quantity)) < quantity:
            raise PaperLedgerSettlementError("inventario no reducible")
        cycle.open_quantity = Decimal(str(cycle.open_quantity)) - quantity
        if cycle.open_quantity == 0:
            cycle.closed_at = moment
        fill_id = f"paper-fill-{uuid4().hex}"
        db.add(
            PaperLedgerFill(
                fill_id=fill_id,
                intent_id=intent_id,
                cycle_id=cycle_id,
                side="SELL",
                quantity=quantity,
                price=normalized_price,
                executed_at=moment,
            )
        )
        fill_ids.append(fill_id)
    intent.state = "FILLED"
    db.flush()
    paper_ledger_transactions_total.labels(operation="settle", outcome="success").inc()
    return tuple(fill_ids)
