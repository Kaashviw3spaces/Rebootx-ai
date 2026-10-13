"""Add durable handoff and idempotent recovery records without changing old data."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('incidents', sa.Column('recovery_reason', sa.String(100), nullable=True))
    op.add_column('incidents', sa.Column('verification_outcome', sa.String(30), nullable=True))
    for table, name in [('recovery_attempts', 'uq_recovery_attempt_logical'), ('audit_logs', 'uq_audit_log_logical')]:
        # Nullable keys preserve historical rows. SQLite requires batch mode
        # when adding a constraint; PostgreSQL alters the table in place.
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('logical_key', sa.String(100), nullable=True))
            if table == 'recovery_attempts':
                batch.add_column(sa.Column('failure_reason', sa.String(100), nullable=True))
            batch.create_unique_constraint(name, ['tenant_id', 'incident_id', 'logical_key'])
    op.create_table('recovery_outbox',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('incident_id', sa.Uuid(), nullable=False),
        sa.Column('temporal_workflow_id', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('lease_token', sa.Uuid(), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['tenant_id', 'incident_id'], ['incidents.tenant_id', 'incidents.id']),
        sa.UniqueConstraint('tenant_id', 'incident_id', name='uq_outbox_incident'),
        sa.UniqueConstraint('temporal_workflow_id'),
    )
    op.create_index('ix_recovery_outbox_tenant_id', 'recovery_outbox', ['tenant_id'])
    op.create_index('ix_recovery_outbox_next_attempt_at', 'recovery_outbox', ['next_attempt_at'])
    # Historical incidents are deliberately not backfilled into active recovery.


def downgrade():
    # Test schemas only: never invoke against a database containing user data.
    op.drop_table('recovery_outbox')
    for table, name in [('audit_logs', 'uq_audit_log_logical'), ('recovery_attempts', 'uq_recovery_attempt_logical')]:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(name, type_='unique')
            batch.drop_column('logical_key')
            if table == 'recovery_attempts':
                batch.drop_column('failure_reason')
    op.drop_column('incidents', 'verification_outcome')
    op.drop_column('incidents', 'recovery_reason')
