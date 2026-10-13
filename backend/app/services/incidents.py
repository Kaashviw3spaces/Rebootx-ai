from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from app.models.entities import AuditLog, Incident, Workflow


def find_duplicate(db, tenant_id, event):
    return db.scalar(select(Incident).where(
        Incident.tenant_id == tenant_id,
        or_(Incident.event_id == event.event_id, and_(
            Incident.source == event.source,
            Incident.source_execution_id == event.source_execution_id,
            Incident.failed_step == event.failed_step,
        )),
    ).order_by(Incident.created_at, Incident.id))


def receive_failure(db, integration, event):
    workflow = db.scalar(select(Workflow).where(
        Workflow.tenant_id == integration.tenant_id,
        Workflow.integration_id == integration.id,
        Workflow.external_id == event.workflow_external_id,
        Workflow.enabled.is_(True),
    ))
    if workflow is None or integration.kind != event.source:
        raise HTTPException(404, "Registered workflow not found")
    existing = find_duplicate(db, integration.tenant_id, event)
    if existing is not None:
        return existing, True
    # Free-form error messages are deliberately discarded at this checkpoint.
    # A denylist cannot reliably sanitize arbitrary PII or opaque credentials.
    incident = Incident(
        tenant_id=integration.tenant_id, integration_id=integration.id,
        workflow_id=workflow.id, event_id=event.event_id, source=event.source,
        source_execution_id=event.source_execution_id, failed_step=event.failed_step,
        operation_id=event.operation_id, failure_type=event.error.category,
        error_details={"category": event.error.category, "message": "[REDACTED]"},
        event_timestamp=event.timestamp, status="RECEIVED",
    )
    try:
        db.add(incident)
        db.flush()
        db.add(AuditLog(
            tenant_id=integration.tenant_id, incident_id=incident.id,
            actor=f"integration:{integration.id}", event_type="INCIDENT_RECEIVED",
            redacted_details={"status": "RECEIVED", "failure_type": event.error.category},
        ))
        db.commit()
    except IntegrityError:
        # A concurrent delivery may have won the unique constraint race.
        db.rollback()
        existing = find_duplicate(db, integration.tenant_id, event)
        if existing is None:
            raise
        return existing, True
    return incident, False
