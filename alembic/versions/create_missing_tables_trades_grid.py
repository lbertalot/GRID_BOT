"""create_missing_tables_trades_grid

Revision ID: create_missing_tables
Revises: 619207adc7fb
Create Date: 2026-01-13 13:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'create_missing_tables'
down_revision: Union[str, None] = '619207adc7fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tablas faltantes que no fueron creadas en migraciones anteriores"""
    connection = op.get_bind()

    # 1. Crear tabla trades si no existe
    result = connection.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'trades'
            );
        """)
    )
    trades_exists = result.scalar()

    if not trades_exists:
        op.create_table(
            'trades',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('symbol', sa.String(), index=True),
            sa.Column('side', sa.String()),  # BUY o SELL
            sa.Column('quantity', sa.Float()),
            sa.Column('entry_price', sa.Float()),
            sa.Column('exit_price', sa.Float(), nullable=True),
            sa.Column('profit_loss', sa.Float(), nullable=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('version', sa.Integer(), nullable=False, server_default='0'),  # Para optimistic locking
        )
        print("✅ Tabla 'trades' creada")

    # 2. Crear tabla grid_config si no existe
    result = connection.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'grid_config'
            );
        """)
    )
    grid_config_exists = result.scalar()

    if not grid_config_exists:
        op.create_table(
            'grid_config',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('symbol', sa.String(), default="BTCUSDT"),
            sa.Column('min_price', sa.Float(), default=20000),
            sa.Column('max_price', sa.Float(), default=30000),
            sa.Column('grids', sa.Integer(), default=5),
            sa.Column('quantity', sa.Float(), default=0.001),
            sa.Column('last_action', sa.String(), nullable=True),
        )
        print("✅ Tabla 'grid_config' creada")

    # 3. Crear tabla asset_limits si no existe
    result = connection.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'asset_limits'
            );
        """)
    )
    asset_limits_exists = result.scalar()

    if not asset_limits_exists:
        op.create_table(
            'asset_limits',
            sa.Column('symbol', sa.String(), primary_key=True),
            sa.Column('min_price', sa.Float(), nullable=False),
            sa.Column('max_price', sa.Float(), nullable=False),
            sa.Column('tick_size', sa.Float(), nullable=False),
            sa.Column('min_qty', sa.Float(), nullable=False),
            sa.Column('max_qty', sa.Float(), nullable=False),
            sa.Column('step_size', sa.Float(), nullable=False),
            sa.Column('min_notional', sa.Float(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        print("✅ Tabla 'asset_limits' creada")

    # 4. Crear tabla system_settings si no existe (diferente de system_config)
    result = connection.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'system_settings'
            );
        """)
    )
    system_settings_exists = result.scalar()

    if not system_settings_exists:
        op.create_table(
            'system_settings',
            sa.Column('key', sa.String(128), primary_key=True, nullable=False),
            sa.Column('value', sa.Text(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.Column('created_at', sa.DateTime(), default=sa.func.now(), nullable=False),
        )
        print("✅ Tabla 'system_settings' creada")

    # 5. Si la tabla trades existe pero no tiene la columna version, agregarla
    if trades_exists:
        result = connection.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'trades'
                    AND column_name = 'version'
                );
            """)
        )
        version_column_exists = result.scalar()

        if not version_column_exists:
            op.add_column('trades', sa.Column('version', sa.Integer(), nullable=False, server_default='0'))
            print("✅ Columna 'version' agregada a tabla 'trades'")


def downgrade() -> None:
    """Eliminar tablas creadas (solo si no tienen datos críticos)"""
    # Verificar si las tablas tienen datos antes de eliminarlas
    # Por seguridad, comentamos el downgrade
    pass
