"""Add tenant-scoped advisory diagnosis records; preserve historical data."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('incident_diagnoses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('incident_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('failure_category', sa.String(50), nullable=False),
        sa.Column('root_cause', sa.String(500), nullable=False),
        sa.Column('explanation', sa.String(1000), nullable=False),
        sa.Column('recommended_action', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('requires_human_approval', sa.Boolean(), nullable=False),
        sa.Column('alternative_actions', sa.JSON(), nullable=False),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('requested_model_id', sa.String(100), nullable=False),
        sa.Column('diagnosed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fallback_reason', sa.String(100), nullable=True),
        sa.Column('policy_reason', sa.String(100), nullable=False),
        sa.Column('recovery_category', sa.String(100), nullable=False),
        sa.Column('allow_fallback', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['tenant_id', 'incident_id'], ['incidents.tenant_id', 'incidents.id']),
        sa.UniqueConstraint('tenant_id', 'incident_id', name='uq_diagnosis_incident'),
        sa.CheckConstraint("status IN ('MOCK','SUCCEEDED','POLICY_REJECTED','FALLBACK','FAILED')", name='ck_diagnosis_status'),
        sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name='ck_diagnosis_confidence'),
    )
    op.create_index('ix_incident_diagnoses_tenant_id', 'incident_diagnoses', ['tenant_id'])


def downgrade():
    # Only disposable test databases; application downgrades are not part of setup.
    op.drop_table('incident_diagnoses')
