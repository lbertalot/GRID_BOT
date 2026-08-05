"""add backtest_runs and backtest_metrics (Passive Income protocol §D)

Revision ID: 20260503_backtest_runs
Revises: 20260426_drop_gridbot_schema
Create Date: 2026-05-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260503_backtest_runs"
down_revision: Union[str, None] = "20260426_drop_gridbot_schema"
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
                AND table_name = 'backtest_runs'
            );
            """
        )
    )
    if r.scalar():
        return

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("strategy_hash", sa.String(length=64), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("cost_model_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="completed",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backtest_runs_strategy_hash",
        "backtest_runs",
        ["strategy_hash"],
        unique=False,
    )
    op.create_index(
        "ix_backtest_runs_symbol",
        "backtest_runs",
        ["symbol"],
        unique=False,
    )
    op.create_index(
        "ix_backtest_runs_name",
        "backtest_runs",
        ["name"],
        unique=False,
    )
    op.create_index(
        "ix_backtest_runs_finished_at",
        "backtest_runs",
        ["finished_at"],
        unique=False,
    )

    op.create_table(
        "backtest_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("backtest_run_id", sa.Integer(), nullable=False),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("sortino_ratio", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("cagr", sa.Float(), nullable=True),
        sa.Column("turnover", sa.Float(), nullable=True),
        sa.Column("after_cost_pnl", sa.Float(), nullable=True),
        sa.Column("total_return", sa.Float(), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("initial_capital", sa.Float(), nullable=True),
        sa.Column("final_capital", sa.Float(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["backtest_run_id"],
            ["backtest_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("backtest_run_id"),
    )
    op.create_index(
        "ix_backtest_metrics_backtest_run_id",
        "backtest_metrics",
        ["backtest_run_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_metrics_backtest_run_id", table_name="backtest_metrics")
    op.drop_table("backtest_metrics")
    op.drop_index("ix_backtest_runs_finished_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_name", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_symbol", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_strategy_hash", table_name="backtest_runs")
    op.drop_table("backtest_runs")
