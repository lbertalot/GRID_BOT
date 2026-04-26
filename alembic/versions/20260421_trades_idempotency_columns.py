"""add_trades_idempotency_columns_and_unique_index

Revision ID: 20260421_trades_idempotency
Revises: create_missing_tables
Create Date: 2026-04-21 14:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260421_trades_idempotency"
down_revision: Union[str, None] = "create_missing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    table_exists = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'trades'
            );
            """
        )
    ).scalar()

    if not table_exists:
        return

    columns = connection.execute(
        sa.text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'trades'
            """
        )
    ).fetchall()
    column_names = {row[0] for row in columns}

    if "order_id" not in column_names:
        op.add_column("trades", sa.Column("order_id", sa.String(length=64), nullable=True))
    if "client_order_id" not in column_names:
        op.add_column("trades", sa.Column("client_order_id", sa.String(length=128), nullable=True))
    if "strategy" not in column_names:
        op.add_column(
            "trades",
            sa.Column("strategy", sa.String(length=50), nullable=True, server_default="grid"),
        )

    # Índice único para deduplicación por order_id del exchange.
    connection.execute(
        sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_order_id ON public.trades(order_id);")
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("DROP INDEX IF EXISTS public.ux_trades_order_id;"))

