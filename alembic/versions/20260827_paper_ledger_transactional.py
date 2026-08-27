"""Paper ledger transaccional: ciclos, fills, intents y reservas.

Revision ID: 20260827_paper_ledger
Revises: 20260505_mc_backtest_fk
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_paper_ledger"
down_revision: Union[str, None] = "20260505_mc_backtest_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_ledger_cycles",
        sa.Column("cycle_id", sa.String(64), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("grid_level", sa.Numeric(24, 12)),
        sa.Column("buy_price", sa.Numeric(24, 12), nullable=False),
        sa.Column("buy_quantity", sa.Numeric(24, 12), nullable=False),
        sa.Column("open_quantity", sa.Numeric(24, 12), nullable=False),
        sa.Column("cost_basis_open_usdt", sa.Numeric(24, 12), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("open_quantity >= 0", name="ck_paper_cycle_open_quantity"),
    )
    op.create_table(
        "paper_ledger_intents",
        sa.Column("intent_id", sa.String(128), primary_key=True),
        sa.Column("client_order_id", sa.String(128), nullable=False, unique=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "paper_ledger_reservations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("intent_id", sa.String(128), nullable=False),
        sa.Column("cycle_id", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 12), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("intent_id", "cycle_id", name="uq_paper_reservation_intent_cycle"),
        sa.ForeignKeyConstraint(["intent_id"], ["paper_ledger_intents.intent_id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["paper_ledger_cycles.cycle_id"]),
        sa.CheckConstraint("quantity > 0", name="ck_paper_reservation_quantity"),
    )
    op.create_table(
        "paper_ledger_fills",
        sa.Column("fill_id", sa.String(128), primary_key=True),
        sa.Column("intent_id", sa.String(128), nullable=False),
        sa.Column("cycle_id", sa.String(64), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 12), nullable=False),
        sa.Column("price", sa.Numeric(24, 12), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["intent_id"], ["paper_ledger_intents.intent_id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["paper_ledger_cycles.cycle_id"]),
        sa.CheckConstraint("quantity > 0", name="ck_paper_fill_quantity"),
        sa.CheckConstraint("price > 0", name="ck_paper_fill_price"),
    )


def downgrade() -> None:
    op.drop_table("paper_ledger_fills")
    op.drop_table("paper_ledger_reservations")
    op.drop_table("paper_ledger_intents")
    op.drop_table("paper_ledger_cycles")
