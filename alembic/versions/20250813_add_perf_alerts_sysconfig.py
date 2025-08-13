from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250813_add_perf_alerts_sysconfig'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'performance_metrics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('total_trades', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('winning_trades', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('losing_trades', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('total_profit', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('total_loss', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('win_rate', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('sharpe_ratio', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('max_drawdown', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False, server_default='INFO'),
        sa.Column('sent_to_telegram', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'system_config',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=100), nullable=False, unique=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('system_config')
    op.drop_table('alerts')
    op.drop_table('performance_metrics')


