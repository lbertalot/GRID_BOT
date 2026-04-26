"""schema_hardening_for_ingestion_tables

Revision ID: 20260421_schema_hardening
Revises: 20260421_trades_idempotency
Create Date: 2026-04-21 15:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260421_schema_hardening"
down_revision: Union[str, None] = "20260421_trades_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(connection, table_name: str) -> bool:
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        ).scalar()
    )


def _has_constraint(connection, table_name: str, constraint_name: str) -> bool:
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = 'public'
                      AND t.relname = :table_name
                      AND c.conname = :constraint_name
                )
                """
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        ).scalar()
    )


def upgrade() -> None:
    connection = op.get_bind()

    # ------------------------------------------------------------------
    # trades: tipos numéricos + constraints de dominio + limpieza índice
    # ------------------------------------------------------------------
    if _table_exists(connection, "trades"):
        # Convertir floats financieros a NUMERIC(20,8)
        op.execute(
            """
            ALTER TABLE public.trades
              ALTER COLUMN quantity TYPE NUMERIC(20,8) USING quantity::numeric,
              ALTER COLUMN entry_price TYPE NUMERIC(20,8) USING entry_price::numeric,
              ALTER COLUMN exit_price TYPE NUMERIC(20,8) USING exit_price::numeric,
              ALTER COLUMN profit_loss TYPE NUMERIC(20,8) USING profit_loss::numeric;
            """
        )

        # Si no hay nulos, endurecer NOT NULL en columnas core
        nulls = connection.execute(
            sa.text(
                """
                SELECT
                  COUNT(*) FILTER (WHERE symbol IS NULL) AS symbol_nulls,
                  COUNT(*) FILTER (WHERE side IS NULL) AS side_nulls,
                  COUNT(*) FILTER (WHERE quantity IS NULL) AS qty_nulls,
                  COUNT(*) FILTER (WHERE entry_price IS NULL) AS entry_nulls
                FROM public.trades
                """
            )
        ).mappings().first()

        if (
            nulls
            and nulls["symbol_nulls"] == 0
            and nulls["side_nulls"] == 0
            and nulls["qty_nulls"] == 0
            and nulls["entry_nulls"] == 0
        ):
            op.execute(
                """
                ALTER TABLE public.trades
                  ALTER COLUMN symbol SET NOT NULL,
                  ALTER COLUMN side SET NOT NULL,
                  ALTER COLUMN quantity SET NOT NULL,
                  ALTER COLUMN entry_price SET NOT NULL;
                """
            )

        # Constraints CHECK (se agregan solo si no existen)
        if not _has_constraint(connection, "trades", "ck_trades_side_allowed"):
            op.execute(
                """
                ALTER TABLE public.trades
                ADD CONSTRAINT ck_trades_side_allowed
                CHECK (side IN ('BUY', 'SELL')) NOT VALID;
                """
            )
            op.execute("ALTER TABLE public.trades VALIDATE CONSTRAINT ck_trades_side_allowed;")

        if not _has_constraint(connection, "trades", "ck_trades_quantity_positive"):
            op.execute(
                """
                ALTER TABLE public.trades
                ADD CONSTRAINT ck_trades_quantity_positive
                CHECK (quantity > 0) NOT VALID;
                """
            )
            op.execute("ALTER TABLE public.trades VALIDATE CONSTRAINT ck_trades_quantity_positive;")

        if not _has_constraint(connection, "trades", "ck_trades_entry_price_positive"):
            op.execute(
                """
                ALTER TABLE public.trades
                ADD CONSTRAINT ck_trades_entry_price_positive
                CHECK (entry_price > 0) NOT VALID;
                """
            )
            op.execute("ALTER TABLE public.trades VALIDATE CONSTRAINT ck_trades_entry_price_positive;")

        # Índice redundante por PK
        op.execute("DROP INDEX IF EXISTS public.ix_trades_id;")

    # ------------------------------------------------------------
    # balances: consistencia temporal + regla de no-negatividad
    # ------------------------------------------------------------
    if _table_exists(connection, "balances"):
        op.execute(
            """
            ALTER TABLE public.balances
              ALTER COLUMN updated_at TYPE TIMESTAMPTZ
              USING updated_at AT TIME ZONE 'UTC',
              ALTER COLUMN updated_at SET DEFAULT now();
            """
        )

        if not _has_constraint(connection, "balances", "ck_balances_amount_non_negative"):
            op.execute(
                """
                ALTER TABLE public.balances
                ADD CONSTRAINT ck_balances_amount_non_negative
                CHECK (amount >= 0) NOT VALID;
                """
            )
            op.execute("ALTER TABLE public.balances VALIDATE CONSTRAINT ck_balances_amount_non_negative;")

    # ------------------------------------------------------------
    # grid_config: defaults + not null + checks de dominio básico
    # ------------------------------------------------------------
    if _table_exists(connection, "grid_config"):
        op.execute(
            """
            UPDATE public.grid_config
            SET
              symbol = COALESCE(symbol, 'BTCUSDT'),
              min_price = COALESCE(min_price, 20000),
              max_price = COALESCE(max_price, 30000),
              grids = COALESCE(grids, 5),
              quantity = COALESCE(quantity, 0.001);
            """
        )
        op.execute(
            """
            ALTER TABLE public.grid_config
              ALTER COLUMN symbol SET DEFAULT 'BTCUSDT',
              ALTER COLUMN min_price SET DEFAULT 20000,
              ALTER COLUMN max_price SET DEFAULT 30000,
              ALTER COLUMN grids SET DEFAULT 5,
              ALTER COLUMN quantity SET DEFAULT 0.001;
            """
        )
        op.execute(
            """
            ALTER TABLE public.grid_config
              ALTER COLUMN symbol SET NOT NULL,
              ALTER COLUMN min_price SET NOT NULL,
              ALTER COLUMN max_price SET NOT NULL,
              ALTER COLUMN grids SET NOT NULL,
              ALTER COLUMN quantity SET NOT NULL;
            """
        )

        if not _has_constraint(connection, "grid_config", "ck_grid_config_price_range"):
            op.execute(
                """
                ALTER TABLE public.grid_config
                ADD CONSTRAINT ck_grid_config_price_range
                CHECK (min_price < max_price) NOT VALID;
                """
            )
            op.execute("ALTER TABLE public.grid_config VALIDATE CONSTRAINT ck_grid_config_price_range;")

        if not _has_constraint(connection, "grid_config", "ck_grid_config_grids_positive"):
            op.execute(
                """
                ALTER TABLE public.grid_config
                ADD CONSTRAINT ck_grid_config_grids_positive
                CHECK (grids > 0) NOT VALID;
                """
            )
            op.execute("ALTER TABLE public.grid_config VALIDATE CONSTRAINT ck_grid_config_grids_positive;")

        if not _has_constraint(connection, "grid_config", "ck_grid_config_quantity_positive"):
            op.execute(
                """
                ALTER TABLE public.grid_config
                ADD CONSTRAINT ck_grid_config_quantity_positive
                CHECK (quantity > 0) NOT VALID;
                """
            )
            op.execute("ALTER TABLE public.grid_config VALIDATE CONSTRAINT ck_grid_config_quantity_positive;")


def downgrade() -> None:
    # Downgrade conservador: no deshace cambios de tipo/NOT NULL por riesgo en producción.
    op.execute("ALTER TABLE public.trades DROP CONSTRAINT IF EXISTS ck_trades_side_allowed;")
    op.execute("ALTER TABLE public.trades DROP CONSTRAINT IF EXISTS ck_trades_quantity_positive;")
    op.execute("ALTER TABLE public.trades DROP CONSTRAINT IF EXISTS ck_trades_entry_price_positive;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trades_id ON public.trades(id);")

    op.execute("ALTER TABLE public.balances DROP CONSTRAINT IF EXISTS ck_balances_amount_non_negative;")

    op.execute("ALTER TABLE public.grid_config DROP CONSTRAINT IF EXISTS ck_grid_config_price_range;")
    op.execute("ALTER TABLE public.grid_config DROP CONSTRAINT IF EXISTS ck_grid_config_grids_positive;")
    op.execute("ALTER TABLE public.grid_config DROP CONSTRAINT IF EXISTS ck_grid_config_quantity_positive;")

