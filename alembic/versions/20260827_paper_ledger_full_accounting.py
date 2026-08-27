"""Completa el esquema contable del ledger paper transaccional.

Revision ID: 20260827_paper_ledger_full
Revises: 20260827_paper_ledger
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_paper_ledger_full"
down_revision: Union[str, None] = "20260827_paper_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AMOUNT = sa.Numeric(24, 12)


def upgrade() -> None:
    op.add_column("paper_ledger_cycles", sa.Column("buy_fee_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_cycles", sa.Column("buy_slippage_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_cycles", sa.Column("buy_fee_remaining", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_cycles", sa.Column("buy_slippage_remaining", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_cycles", sa.Column("closed_quantity", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_cycles", sa.Column("sell_notional_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_cycles", sa.Column("gross_pnl_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_cycles", sa.Column("net_pnl_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_cycles", sa.Column("fees_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_cycles", sa.Column("slippage_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_fills", sa.Column("symbol", sa.String(32), nullable=False, server_default=""))
    op.add_column("paper_ledger_fills", sa.Column("order_type", sa.String(16), nullable=False, server_default="LIMIT"))
    op.add_column("paper_ledger_fills", sa.Column("notional_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_fills", sa.Column("commission_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_fills", sa.Column("slippage_usdt", _AMOUNT, nullable=False, server_default="0"))
    op.add_column("paper_ledger_fills", sa.Column("grid_level", _AMOUNT))
    op.create_table(
        "paper_ledger_accounts",
        sa.Column("window_id", sa.String(64), primary_key=True),
        sa.Column("schema_version", sa.Integer, nullable=False),
        sa.Column("quote_asset", sa.String(16), nullable=False),
        sa.Column("initial_cash", _AMOUNT, nullable=False),
        sa.Column("cash", _AMOUNT, nullable=False),
        sa.Column("deployed_capital", _AMOUNT, nullable=False),
        sa.Column("realized_gross_pnl_usdt", _AMOUNT, nullable=False),
        sa.Column("realized_net_pnl_usdt", _AMOUNT, nullable=False),
        sa.Column("fees_total_usdt", _AMOUNT, nullable=False),
        sa.Column("slippage_total_usdt", _AMOUNT, nullable=False),
        sa.Column("cost_model_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "paper_ledger_fill_cycles",
        sa.Column("fill_id", sa.String(128), sa.ForeignKey("paper_ledger_fills.fill_id"), primary_key=True),
        sa.Column("cycle_id", sa.String(64), sa.ForeignKey("paper_ledger_cycles.cycle_id"), primary_key=True),
        sa.Column("quantity", _AMOUNT, nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_paper_fill_cycle_quantity"),
    )
    op.create_table(
        "paper_ledger_equity_samples",
        sa.Column("sample_id", sa.String(64), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("equity", _AMOUNT, nullable=False),
        sa.Column("cash", _AMOUNT, nullable=False),
        sa.Column("inventory_value", _AMOUNT, nullable=False),
        sa.Column("deployed_capital", _AMOUNT, nullable=False),
        sa.Column("config_hash", sa.String(64)),
        sa.Column("daily_close_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("paper_ledger_equity_samples")
    op.drop_table("paper_ledger_fill_cycles")
    op.drop_table("paper_ledger_accounts")
    for column in ("grid_level", "slippage_usdt", "commission_usdt", "notional_usdt", "order_type", "symbol"):
        op.drop_column("paper_ledger_fills", column)
    for column in ("slippage_usdt", "fees_usdt", "net_pnl_usdt", "gross_pnl_usdt", "sell_notional_usdt", "closed_quantity", "buy_slippage_remaining", "buy_fee_remaining", "buy_slippage_usdt", "buy_fee_usdt"):
        op.drop_column("paper_ledger_cycles", column)
