"""monte_carlo_runs.backtest_run_id FK a backtest_runs

Revision ID: 20260505_mc_backtest_fk
Revises: 20260504_mc_runs
Create Date: 2026-05-05

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260505_mc_backtest_fk"
down_revision: Union[str, None] = "20260504_mc_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("monte_carlo_runs")}
    if "backtest_run_id" not in cols:
        with op.batch_alter_table("monte_carlo_runs") as batch_op:
            batch_op.add_column(
                sa.Column("backtest_run_id", sa.Integer(), nullable=True)
            )
            batch_op.create_index(
                "ix_monte_carlo_runs_backtest_run_id",
                ["backtest_run_id"],
                unique=False,
            )
            batch_op.create_foreign_key(
                "fk_monte_carlo_runs_backtest_run_id",
                "backtest_runs",
                ["backtest_run_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("monte_carlo_runs")}
    if "backtest_run_id" in cols:
        with op.batch_alter_table("monte_carlo_runs") as batch_op:
            batch_op.drop_constraint(
                "fk_monte_carlo_runs_backtest_run_id", type_="foreignkey"
            )
            batch_op.drop_index("ix_monte_carlo_runs_backtest_run_id")
            batch_op.drop_column("backtest_run_id")
