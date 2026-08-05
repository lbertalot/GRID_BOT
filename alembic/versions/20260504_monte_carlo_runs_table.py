"""add monte_carlo_runs (Passive Income Fase C — registro MC)

Revision ID: 20260504_mc_runs
Revises: 20260503_backtest_runs
Create Date: 2026-05-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260504_mc_runs"
down_revision: Union[str, None] = "20260503_backtest_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    r = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'monte_carlo_runs'
            );
            """
        )
    )
    if r.scalar():
        return

    op.create_table(
        "monte_carlo_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("n_paths", sa.Integer(), nullable=False),
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("bootstrap_mode", sa.String(length=16), nullable=False),
        sa.Column("block_size", sa.Integer(), nullable=True),
        sa.Column(
            "shock_single_day_gross_multiplier",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "shock_three_day_run_gross_multiplier",
            sa.Float(),
            nullable=True,
        ),
        sa.Column("baseline_max_drawdown", sa.Float(), nullable=False),
        sa.Column("mean_max_drawdown", sa.Float(), nullable=False),
        sa.Column("p95_max_drawdown", sa.Float(), nullable=False),
        sa.Column("worst_max_drawdown", sa.Float(), nullable=False),
        sa.Column("historical_returns_length", sa.Integer(), nullable=True),
        sa.Column("study_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_monte_carlo_runs_symbol",
        "monte_carlo_runs",
        ["symbol"],
        unique=False,
    )
    op.create_index(
        "ix_monte_carlo_runs_created_at",
        "monte_carlo_runs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_monte_carlo_runs_created_at", table_name="monte_carlo_runs")
    op.drop_index("ix_monte_carlo_runs_symbol", table_name="monte_carlo_runs")
    op.drop_table("monte_carlo_runs")
