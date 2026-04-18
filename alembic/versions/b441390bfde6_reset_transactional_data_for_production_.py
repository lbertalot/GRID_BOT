"""Reset transactional data for production rebuild

Revision ID: b441390bfde6
Revises: add_perf_alerts_cfg
Create Date: 2025-09-18 22:32:09.596644

⚠️  WARNING: This migration will DELETE ALL TRANSACTIONAL DATA
This includes:
- All trades
- All positions  
- All PnL history
- All alerts
- All reconciliation logs

This is a DESTRUCTIVE operation that cannot be undone.
Only run this migration if you want to start fresh for production.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b441390bfde6'
down_revision: Union[str, None] = 'add_perf_alerts_cfg'

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Reset all transactional data for production rebuild.
    
    This function will:
    1. Truncate all transactional tables
    2. Reset sequences to start from 1
    3. Keep configuration tables intact
    """
    
    # List of transactional tables to reset
    transactional_tables = [
        'trades',
        'positions', 
        'pnl_history',
        'alerts',
        'reconciliation_logs',
        'system_events',
        'operation_tracking'
    ]
    
    # Check if tables exist before truncating
    connection = op.get_bind()
    
    for table_name in transactional_tables:
        # Check if table exists
        result = connection.execute(
            sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = :table_name
                );
            """), 
            {"table_name": table_name}
        )
        
        table_exists = result.scalar()
        
        if table_exists:
            # Truncate table and reset sequence
            op.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")
            print(f"✅ Reset table: {table_name}")
        else:
            print(f"⚠️  Table {table_name} does not exist, skipping...")
    
    # Reset system settings to default values
    # Nota: La tabla se llama system_config, no system_settings
    # Solo actualizamos si la tabla existe (puede no existir en nuevas instalaciones)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'system_config') THEN
                UPDATE system_config 
                SET value = '0.0' 
                WHERE key = 'portfolio:baseline_value_usdt';
                
                UPDATE system_config 
                SET value = NOW()::text 
                WHERE key = 'profit:baseline_iso';
            END IF;
        END $$;
    """)
    
    print("✅ System settings reset to defaults")
    print("🚨 WARNING: All transactional data has been deleted!")
    print("📊 System is now ready for fresh production deployment")


def downgrade() -> None:
    """
    This migration cannot be downgraded as it deletes data.
    Data recovery would require restoring from backup.
    """
    raise NotImplementedError(
        "This migration cannot be downgraded as it deletes transactional data. "
        "To recover data, restore from a backup taken before this migration."
    )
