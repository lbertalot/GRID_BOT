"""Modelos transaccionales del ledger PAPER.

Los importes monetarios permanecen en NUMERIC/Decimal; no se usan para live.
"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint

from app.models.base import Base


class PaperLedgerCycle(Base):
    __tablename__ = "paper_ledger_cycles"
    cycle_id = Column(String(64), primary_key=True)
    symbol = Column(String(32), nullable=False, index=True)
    grid_level = Column(Numeric(24, 12))
    buy_price = Column(Numeric(24, 12), nullable=False)
    buy_quantity = Column(Numeric(24, 12), nullable=False)
    open_quantity = Column(Numeric(24, 12), nullable=False)
    cost_basis_open_usdt = Column(Numeric(24, 12), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("open_quantity >= 0", name="ck_paper_cycle_open_quantity"),)


class PaperLedgerIntent(Base):
    __tablename__ = "paper_ledger_intents"
    intent_id = Column(String(128), primary_key=True)
    client_order_id = Column(String(128), nullable=False, unique=True)
    symbol = Column(String(32), nullable=False)
    side = Column(String(4), nullable=False)
    state = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class PaperLedgerReservation(Base):
    __tablename__ = "paper_ledger_reservations"
    id = Column(Integer, primary_key=True)
    intent_id = Column(String(128), ForeignKey("paper_ledger_intents.intent_id"), nullable=False)
    cycle_id = Column(String(64), ForeignKey("paper_ledger_cycles.cycle_id"), nullable=False)
    quantity = Column(Numeric(24, 12), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("intent_id", "cycle_id", name="uq_paper_reservation_intent_cycle"),
        CheckConstraint("quantity > 0", name="ck_paper_reservation_quantity"),
    )


class PaperLedgerFill(Base):
    __tablename__ = "paper_ledger_fills"
    fill_id = Column(String(128), primary_key=True)
    intent_id = Column(String(128), ForeignKey("paper_ledger_intents.intent_id"), nullable=False)
    cycle_id = Column(String(64), ForeignKey("paper_ledger_cycles.cycle_id"), nullable=False)
    side = Column(String(4), nullable=False)
    quantity = Column(Numeric(24, 12), nullable=False)
    price = Column(Numeric(24, 12), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_paper_fill_quantity"),
        CheckConstraint("price > 0", name="ck_paper_fill_price"),
    )
