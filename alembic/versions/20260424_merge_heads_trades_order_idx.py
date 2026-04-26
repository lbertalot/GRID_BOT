"""merge alembic heads; normalize unique indexes for ON CONFLICT

Revision ID: 20260424_merge_trades_idx
Revises: 20260421_schema_hardening, a1b2c3d4e5f6
Create Date: 2026-04-24 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_merge_trades_idx"
down_revision: Union[str, None, tuple] = ("20260421_schema_hardening", "a1b2c3d4e5f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(connection, table: str) -> bool:
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = :t
                )
                """
            ),
            {"t": table},
        ).scalar()
    )


def upgrade() -> None:
    connection = op.get_bind()

    if _table_exists(connection, "trades"):
        # Reemplaza índices posiblemente creados con distintos nombres/definiciones.
        op.execute("DROP INDEX IF EXISTS public.ux_trades_order_id_not_null;")
        op.execute("DROP INDEX IF EXISTS public.ux_trades_order_id;")
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_order_id
            ON public.trades (order_id);
            """
        )

    if _table_exists(connection, "balances"):
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_balances_asset
            ON public.balances (asset);
            """
        )


def downgrade() -> None:
    connection = op.get_bind()
    op.execute("DROP INDEX IF EXISTS public.ux_balances_asset;")
    op.execute("DROP INDEX IF EXISTS public.ux_trades_order_id;")
    if _table_exists(connection, "trades"):
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_order_id ON public.trades (order_id);"
        )
