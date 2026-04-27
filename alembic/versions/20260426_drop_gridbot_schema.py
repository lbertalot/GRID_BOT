"""Drop duplicate gridbot schema

Revision ID: 20260426_drop_gridbot_schema
Revises: 20260424_merge_trades_order_idx
Create Date: 2026-04-26

"""
from alembic import op

revision = "20260426_drop_gridbot_schema"
down_revision = "20260424_merge_trades_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS gridbot CASCADE")


def downgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS gridbot")
