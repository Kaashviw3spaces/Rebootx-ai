"""Pin incident recovery mode and add durable external action reservations."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('incidents', sa.Column('recovery_mode', sa.String(30), nullable=False, server_default='mock-only'))
    op.add_column('recovery_attempts', sa.Column('external_action_key', sa.String(64), nullable=True))
    op.add_column('recovery_attempts', sa.Column('evidence', sa.JSON(), nullable=True))
    op.create_index('uq_external_action_key', 'recovery_attempts', ['external_action_key'], unique=True)


def downgrade():
    op.drop_index('uq_external_action_key', table_name='recovery_attempts')
    op.drop_column('recovery_attempts', 'evidence')
    op.drop_column('recovery_attempts', 'external_action_key')
    op.drop_column('incidents', 'recovery_mode')
