"""Modelos transaccionales del ledger PAPER.

Los importes monetarios permanecen en NUMERIC/Decimal; no se usan para live.
"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint

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
    buy_fee_usdt = Column(Numeric(24, 12), nullable=False, default=0)
    buy_slippage_usdt = Column(Numeric(24, 12), nullable=False, default=0)
    buy_fee_remaining = Column(Numeric(24, 12), nullable=False, default=0)
    buy_slippage_remaining = Column(Numeric(24, 12), nullable=False, default=0)
    closed_quantity = Column(Numeric(24, 12), nullable=False, default=0)
    sell_notional_usdt = Column(Numeric(24, 12), nullable=False, default=0)
    gross_pnl_usdt = Column(Numeric(24, 12), nullable=False, default=0)
    net_pnl_usdt = Column(Numeric(24, 12), nullable=False, default=0)
    fees_usdt = Column(Numeric(24, 12), nullable=False, default=0)
    slippage_usdt = Column(Numeric(24, 12), nullable=False, default=0)
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
    symbol = Column(String(32), nullable=False, default="")
    order_type = Column(String(16), nullable=False, default="LIMIT")
    notional_usdt = Column(Numeric(24, 12), nullable=False, default=0)
    commission_usdt = Column(Numeric(24, 12), nullable=False, default=0)
    slippage_usdt = Column(Numeric(24, 12), nullable=False, default=0)
    grid_level = Column(Numeric(24, 12))
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_paper_fill_quantity"),
        CheckConstraint("price > 0", name="ck_paper_fill_price"),
    )


class PaperLedgerAccount(Base):
    """Snapshot auditable de la cuenta paper de una ventana."""

    __tablename__ = "paper_ledger_accounts"
    window_id = Column(String(64), primary_key=True)
    schema_version = Column(Integer, nullable=False)
    quote_asset = Column(String(16), nullable=False)
    initial_cash = Column(Numeric(24, 12), nullable=False)
    cash = Column(Numeric(24, 12), nullable=False)
    deployed_capital = Column(Numeric(24, 12), nullable=False)
    realized_gross_pnl_usdt = Column(Numeric(24, 12), nullable=False)
    realized_net_pnl_usdt = Column(Numeric(24, 12), nullable=False)
    fees_total_usdt = Column(Numeric(24, 12), nullable=False)
    slippage_total_usdt = Column(Numeric(24, 12), nullable=False)
    cost_model_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class PaperLedgerFillCycle(Base):
    """Asignación explícita de un fill a uno o más ciclos FIFO."""

    __tablename__ = "paper_ledger_fill_cycles"
    fill_id = Column(String(128), ForeignKey("paper_ledger_fills.fill_id"), primary_key=True)
    cycle_id = Column(String(64), ForeignKey("paper_ledger_cycles.cycle_id"), primary_key=True)
    quantity = Column(Numeric(24, 12), nullable=False)
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_paper_fill_cycle_quantity"),)


class PaperLedgerEquitySample(Base):
    """Muestra MtM idempotente del ledger paper."""

    __tablename__ = "paper_ledger_equity_samples"
    sample_id = Column(String(64), primary_key=True)
    at = Column(DateTime(timezone=True), nullable=False, index=True)
    equity = Column(Numeric(24, 12), nullable=False)
    cash = Column(Numeric(24, 12), nullable=False)
    inventory_value = Column(Numeric(24, 12), nullable=False)
    deployed_capital = Column(Numeric(24, 12), nullable=False)
    config_hash = Column(String(64))
    daily_close_at = Column(DateTime(timezone=True))
