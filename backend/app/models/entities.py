import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, JSON, String, UniqueConstraint, Uuid
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


class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "incident_id"], ["incidents.tenant_id", "incidents.id"]),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(100))
    adapter: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str | None] = mapped_column(String(50))
    external_reference: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "incident_id"], ["incidents.tenant_id", "incidents.id"]),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    actor: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(100))
    redacted_details: Mapped[dict] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
