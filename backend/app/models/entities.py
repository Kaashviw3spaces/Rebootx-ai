import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, ForeignKeyConstraint, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    read_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("tenant_id", "id"), UniqueConstraint("secret_ref"))
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="n8n")
    secret_ref: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "integration_id", "external_id"),
        ForeignKeyConstraint(["tenant_id", "integration_id"], ["integrations.tenant_id", "integrations.id"]),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    integration_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    external_id: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(50), default="notification_v1")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "event_id", name="uq_incident_event"),
        UniqueConstraint("tenant_id", "source", "source_execution_id", "failed_step", name="uq_incident_execution_step"),
        ForeignKeyConstraint(["tenant_id", "workflow_id"], ["workflows.tenant_id", "workflows.id"]),
        ForeignKeyConstraint(["tenant_id", "integration_id"], ["integrations.tenant_id", "integrations.id"]),
        CheckConstraint("status IN ('RECEIVED','VALIDATING','DIAGNOSING','PLANNED','EXECUTING','VERIFYING','RECOVERED','NEEDS_ATTENTION')", name="ck_incident_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    integration_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    workflow_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    event_id: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(30))
    source_execution_id: Mapped[str] = mapped_column(String(200))
    failed_step: Mapped[str] = mapped_column(String(200))
    operation_id: Mapped[str] = mapped_column(String(200))
    failure_type: Mapped[str] = mapped_column(String(100))
    error_details: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED")
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_reason: Mapped[str | None] = mapped_column(String(100))
    verification_outcome: Mapped[str | None] = mapped_column(String(30))


class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "incident_id"], ["incidents.tenant_id", "incidents.id"]),
        UniqueConstraint('tenant_id', 'incident_id', 'logical_key', name='uq_recovery_attempt_logical'),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(100))
    adapter: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str | None] = mapped_column(String(50))
    external_reference: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    logical_key: Mapped[str | None] = mapped_column(String(100))
    failure_reason: Mapped[str | None] = mapped_column(String(100))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "incident_id"], ["incidents.tenant_id", "incidents.id"]),
        UniqueConstraint('tenant_id', 'incident_id', 'logical_key', name='uq_audit_log_logical'),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    actor: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(100))
    redacted_details: Mapped[dict] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    logical_key: Mapped[str | None] = mapped_column(String(100))


class RecoveryOutbox(Base):
    __tablename__ = 'recovery_outbox'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id', 'incident_id'], ['incidents.tenant_id', 'incidents.id']),
        UniqueConstraint('tenant_id', 'incident_id', name='uq_outbox_incident'),
        UniqueConstraint('temporal_workflow_id'),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('tenants.id'), index=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    temporal_workflow_id: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    attempt_count: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(100))


class IncidentDiagnosis(Base):
    __tablename__ = 'incident_diagnoses'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id', 'incident_id'], ['incidents.tenant_id', 'incidents.id']),
        UniqueConstraint('tenant_id', 'incident_id', name='uq_diagnosis_incident'),
        CheckConstraint("status IN ('MOCK','SUCCEEDED','POLICY_REJECTED','FALLBACK','FAILED')", name='ck_diagnosis_status'),
        CheckConstraint('confidence >= 0 AND confidence <= 1', name='ck_diagnosis_confidence'),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('tenants.id'), index=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(30))
    failure_category: Mapped[str] = mapped_column(String(50))
    root_cause: Mapped[str] = mapped_column(String(500))
    explanation: Mapped[str] = mapped_column(String(1000))
    recommended_action: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean)
    alternative_actions: Mapped[list] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(20))
    model_id: Mapped[str] = mapped_column(String(100))
    requested_model_id: Mapped[str] = mapped_column(String(100))
    diagnosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    fallback_reason: Mapped[str | None] = mapped_column(String(100))
    policy_reason: Mapped[str] = mapped_column(String(100))
    recovery_category: Mapped[str] = mapped_column(String(100))
    allow_fallback: Mapped[bool] = mapped_column(Boolean)

    @property
    def source(self) -> str:
        # Also label historical fallback rows correctly without a backfill/migration.
        if self.status in {'MOCK', 'FALLBACK', 'FAILED'} or self.model_id == 'mock-diagnosis-v1':
            return 'mock'
        if self.model_id == 'deterministic-diagnosis-v1':
            return 'deterministic'
        return self.provider if self.provider in {'gemma', 'mock', 'deterministic'} else 'unknown'
