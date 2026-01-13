"""add_version_column_for_optimistic_locking

Revision ID: 619207adc7fb
Revises: b441390bfde6
Create Date: 2026-01-02 23:13:00.557207

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '619207adc7fb'
down_revision: Union[str, None] = 'b441390bfde6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agregar columna version para optimistic locking"""
    
    # 1. Agregar columna version a tabla trades (solo si existe)
    # Verificar si la tabla trades existe antes de agregar la columna
    connection = op.get_bind()
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'trades'
            );
        """)
    )
    trades_exists = result.scalar()
    
    if trades_exists:
        # Verificar si la columna ya existe
        result = connection.execute(
            sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'trades' 
                    AND column_name = 'version'
                );
            """)
        )
        column_exists = result.scalar()
        
        if not column_exists:
            op.add_column('trades', sa.Column('version', sa.Integer(), nullable=False, server_default='0'))
    else:
        print("⚠️  Tabla 'trades' no existe, saltando agregado de columna 'version'")
    
    # 2. Crear tabla balances con columna version
    op.create_table(
        'balances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset', sa.String(20), unique=True, nullable=False),
        sa.Column('amount', sa.Numeric(20, 8), nullable=False, server_default='0'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    
    # 3. Crear índice en asset
    op.create_index('ix_balances_asset', 'balances', ['asset'])


def downgrade() -> None:
    """Revertir cambios"""
    # Verificar si las tablas/columnas existen antes de eliminarlas
    connection = op.get_bind()
    
    # Eliminar índice si existe
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND indexname = 'ix_balances_asset'
            );
        """)
    )
    if result.scalar():
        op.drop_index('ix_balances_asset', table_name='balances')
    
    # Eliminar tabla balances si existe
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'balances'
            );
        """)
    )
    if result.scalar():
        op.drop_table('balances')
    
    # Eliminar columna version de trades si existe
    result = connection.execute(
        sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'trades' 
                AND column_name = 'version'
            );
        """)
    )
    if result.scalar():
        op.drop_column('trades', 'version')

