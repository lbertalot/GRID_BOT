"""Tests offline del servicio transaccional del ledger PAPER."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.paper_ledger import (
    PaperLedgerCycle,
    PaperLedgerFill,
    PaperLedgerIntent,
    PaperLedgerReservation,
)
from app.services.paper_ledger_repository import (
    PaperLedgerFillAllocation,
    PaperLedgerReservationError,
    PaperLedgerSettlementError,
    reserve_reduce_only,
    settle_reduce_only,
)


@pytest.fixture
def memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _cycle(cycle_id: str, quantity: str = "1") -> PaperLedgerCycle:
    return PaperLedgerCycle(
        cycle_id=cycle_id,
        symbol="BTCUSDT",
        grid_level=Decimal("60000"),
        buy_price=Decimal("60000"),
        buy_quantity=Decimal(quantity),
        open_quantity=Decimal(quantity),
        cost_basis_open_usdt=Decimal(quantity) * Decimal("60000"),
        opened_at=datetime.now(timezone.utc),
    )


def test_reserve_reduce_only_is_idempotent_and_uses_decimal(memory_session) -> None:
    memory_session.add(_cycle("cycle-a", "0.5"))
    memory_session.commit()

    first = reserve_reduce_only(
        memory_session,
        symbol="btcusdt",
        allocations={"cycle-a": Decimal("0.2")},
        client_order_id="paper-sell-1",
    )
    duplicate = reserve_reduce_only(
        memory_session,
        symbol="BTCUSDT",
        allocations={"cycle-a": Decimal("0.2")},
        client_order_id="paper-sell-1",
    )

    assert duplicate == first
    assert memory_session.query(PaperLedgerIntent).count() == 1
    reservation = memory_session.query(PaperLedgerReservation).one()
    assert Decimal(str(reservation.quantity)) == Decimal("0.2")


def test_active_reservation_prevents_overselling_inventory(memory_session) -> None:
    memory_session.add(_cycle("cycle-a", "0.5"))
    memory_session.commit()
    reserve_reduce_only(
        memory_session,
        symbol="BTCUSDT",
        allocations={"cycle-a": Decimal("0.4")},
        client_order_id="paper-sell-1",
    )

    with pytest.raises(PaperLedgerReservationError, match="inventario no reducible"):
        reserve_reduce_only(
            memory_session,
            symbol="BTCUSDT",
            allocations={"cycle-a": Decimal("0.2")},
            client_order_id="paper-sell-2",
        )

    assert memory_session.query(PaperLedgerIntent).count() == 1


def test_expired_reservation_does_not_hold_inventory(memory_session) -> None:
    memory_session.add_all(
        [
            _cycle("cycle-a", "0.5"),
            PaperLedgerIntent(
                intent_id="expired",
                client_order_id="expired-sell",
                symbol="BTCUSDT",
                side="SELL",
                state="RESERVED",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            ),
            PaperLedgerReservation(
                intent_id="expired",
                cycle_id="cycle-a",
                quantity=Decimal("0.5"),
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            ),
        ]
    )
    memory_session.commit()

    intent_id = reserve_reduce_only(
        memory_session,
        symbol="BTCUSDT",
        allocations={"cycle-a": Decimal("0.5")},
        client_order_id="fresh-sell",
    )

    assert intent_id.startswith("reduce-")


def test_settle_reduce_only_records_fills_and_closes_cycle(memory_session) -> None:
    memory_session.add(_cycle("cycle-a", "0.5"))
    memory_session.commit()
    intent_id = reserve_reduce_only(
        memory_session,
        symbol="BTCUSDT",
        allocations={"cycle-a": Decimal("0.5")},
        client_order_id="paper-sell-1",
    )

    fill_ids = settle_reduce_only(
        memory_session,
        intent_id=intent_id,
        allocations=(PaperLedgerFillAllocation("cycle-a", Decimal("0.5")),),
        price=Decimal("61000"),
    )

    assert len(fill_ids) == 1
    assert memory_session.query(PaperLedgerIntent).one().state == "FILLED"
    assert Decimal(str(memory_session.query(PaperLedgerCycle).one().open_quantity)) == Decimal("0")
    assert memory_session.query(PaperLedgerCycle).one().closed_at is not None
    fill = memory_session.query(PaperLedgerFill).one()
    assert fill.side == "SELL"
    assert Decimal(str(fill.price)) == Decimal("61000")


def test_settlement_is_idempotent_after_persisted_fill(memory_session) -> None:
    memory_session.add(_cycle("cycle-a", "0.5"))
    memory_session.commit()
    intent_id = reserve_reduce_only(
        memory_session,
        symbol="BTCUSDT",
        allocations={"cycle-a": Decimal("0.5")},
        client_order_id="paper-sell-1",
    )
    first = settle_reduce_only(
        memory_session,
        intent_id=intent_id,
        allocations=(PaperLedgerFillAllocation("cycle-a", Decimal("0.5")),),
        price=Decimal("61000"),
    )
    second = settle_reduce_only(
        memory_session,
        intent_id=intent_id,
        allocations=(PaperLedgerFillAllocation("cycle-a", Decimal("0.5")),),
        price=Decimal("61000"),
    )

    assert second == first
    assert memory_session.query(PaperLedgerFill).count() == 1


def test_invalid_or_expired_settlement_fails_without_reducing_cycle(memory_session) -> None:
    memory_session.add(_cycle("cycle-a", "0.5"))
    memory_session.commit()
    intent_id = reserve_reduce_only(
        memory_session,
        symbol="BTCUSDT",
        allocations={"cycle-a": Decimal("0.5")},
        client_order_id="paper-sell-1",
    )
    reservation = memory_session.query(PaperLedgerReservation).one()
    reservation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    memory_session.commit()

    with pytest.raises(PaperLedgerSettlementError, match="reserva vencida"):
        settle_reduce_only(
            memory_session,
            intent_id=intent_id,
            allocations=(PaperLedgerFillAllocation("cycle-a", Decimal("0.5")),),
            price=Decimal("61000"),
        )

    cycle = memory_session.query(PaperLedgerCycle).one()
    assert Decimal(str(cycle.open_quantity)) == Decimal("0.5")
    assert memory_session.query(PaperLedgerFill).count() == 0


def test_float_money_is_rejected_before_database_mutation(memory_session) -> None:
    memory_session.add(_cycle("cycle-a", "0.5"))
    memory_session.commit()

    with pytest.raises(PaperLedgerReservationError, match="Decimal"):
        reserve_reduce_only(
            memory_session,
            symbol="BTCUSDT",
            allocations={"cycle-a": 0.5},
            client_order_id="paper-sell-1",
        )

    assert memory_session.query(PaperLedgerIntent).count() == 0
