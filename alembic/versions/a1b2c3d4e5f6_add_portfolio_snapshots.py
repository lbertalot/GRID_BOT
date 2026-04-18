"""add_portfolio_snapshots

Revision ID: a1b2c3d4e5f6
Revises: create_missing_tables
Create Date: 2026-04-17 00:00:00.000000

Crea la tabla portfolio_snapshots usada por portfolio-snapshot-agent
para registrar el valor total del portafolio cada 15 minutos.
Esto reemplaza los datos simulados (np.random) en performance_analyzer.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "create_missing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # Verificar que la tabla no existe antes de crearla (idempotente)
    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'portfolio_snapshots'
            );
            """
        )
    )
    if result.scalar():
        print("⚠️  Tabla 'portfolio_snapshots' ya existe, saltando creación")
        return

    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("total_value_usdt", sa.Float(), nullable=False),
        sa.Column("usdt_free", sa.Float(), nullable=False, server_default="0"),
        sa.Column("btc_value_usdt", sa.Float(), nullable=False, server_default="0"),
        sa.Column("other_assets_usdt", sa.Float(), nullable=False, server_default="0"),
        sa.Column("btc_price", sa.Float(), nullable=True),
        sa.Column("primary_symbol", sa.String(20), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Índice para queries de rango temporal (get_portfolio_value_history)
    op.create_index(
        "ix_portfolio_snapshots_captured_at",
        "portfolio_snapshots",
        ["captured_at"],
    )

    print("✅ Tabla 'portfolio_snapshots' creada con índice temporal")


def downgrade() -> None:
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE schemaname = 'public'
                AND indexname = 'ix_portfolio_snapshots_captured_at'
            );
            """
        )
    )
    if result.scalar():
        op.drop_index("ix_portfolio_snapshots_captured_at", table_name="portfolio_snapshots")

    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'portfolio_snapshots'
            );
            """
        )
    )
    if result.scalar():
        op.drop_table("portfolio_snapshots")
