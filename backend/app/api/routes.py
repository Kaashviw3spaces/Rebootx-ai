from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select

from app.core.security import authenticate_reader, authenticate_webhook
from app.models.entities import Incident, RecoveryAttempt, AuditLog, RecoveryOutbox
from app.schemas.events import FailureEvent, IncidentResponse, IngestionResponse
from app.services.incidents import receive_failure
from app.schemas.recovery import RecoveryResponse, AttemptResponse, TimelineResponse

router = APIRouter()


def get_db(request: Request):
    with request.app.state.sessions() as db:
        yield db


@router.get("/health")
def health():
    # Liveness only; migrations and DB connectivity are separate checks.
    return {"status": "ok"}


@router.post("/api/v1/events/failure", status_code=202, response_model=IngestionResponse)
async def failure(request: Request, db=Depends(get_db)):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > request.app.state.settings.max_webhook_body_bytes:
            raise HTTPException(413, "Event body too large")
    integration, _ = authenticate_webhook(
        db, request.headers.get("X-Integration-ID"), request.headers.get("X-Webhook-Signature"), bytes(raw),
    )
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "Expected application/json")
    try:
        event = FailureEvent.model_validate_json(bytes(raw))
    except ValidationError:
        # Never echo the untrusted payload or validation input back to a caller.
        raise HTTPException(422, "Malformed failure event") from None
    age = abs((datetime.now(timezone.utc) - event.timestamp).total_seconds())
    if age > request.app.state.settings.webhook_timestamp_tolerance_seconds:
        raise HTTPException(401, "Event timestamp outside allowed tolerance")
    incident, duplicate = receive_failure(db, integration, event)
    return IngestionResponse(incident_id=incident.id, status=incident.status, duplicate=duplicate)


@router.get("/api/v1/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: UUID, request: Request, db=Depends(get_db)):
    return authorized_incident(db, request, incident_id)


def authorized_incident(db, request, incident_id):
    tenant = authenticate_reader(db, request.headers.get("Authorization"))
    incident = db.scalar(select(Incident).where(Incident.id == incident_id, Incident.tenant_id == tenant.id))
    if incident is None:
        raise HTTPException(404, "Incident not found")
    return incident


@router.get('/api/v1/incidents/{incident_id}/recovery', response_model=RecoveryResponse)
def get_recovery(incident_id: UUID, request: Request, db=Depends(get_db)):
    incident = authorized_incident(db, request, incident_id)
    outbox = db.scalar(select(RecoveryOutbox).where(
        RecoveryOutbox.tenant_id == incident.tenant_id, RecoveryOutbox.incident_id == incident.id))
    return RecoveryResponse(
        incident_id=incident.id, status=incident.status,
        verification_outcome=incident.verification_outcome, escalation_reason=incident.recovery_reason,
        temporal_workflow_id=outbox.temporal_workflow_id if outbox else None,
        dispatch_status=('DISPATCHED' if outbox.dispatched_at else 'PENDING') if outbox else 'NOT_QUEUED',
        dispatch_attempts=outbox.attempt_count if outbox else 0,
        dispatch_error=outbox.last_error if outbox else None,
    )


@router.get('/api/v1/incidents/{incident_id}/attempts', response_model=list[AttemptResponse])
def get_attempts(incident_id: UUID, request: Request, db=Depends(get_db)):
    incident = authorized_incident(db, request, incident_id)
    return db.scalars(select(RecoveryAttempt).where(
        RecoveryAttempt.tenant_id == incident.tenant_id, RecoveryAttempt.incident_id == incident.id,
    ).order_by(RecoveryAttempt.started_at, RecoveryAttempt.id)).all()


@router.get('/api/v1/incidents/{incident_id}/timeline', response_model=list[TimelineResponse])
def get_timeline(incident_id: UUID, request: Request, db=Depends(get_db)):
    incident = authorized_incident(db, request, incident_id)
    return db.scalars(select(AuditLog).where(
        AuditLog.tenant_id == incident.tenant_id, AuditLog.incident_id == incident.id,
    ).order_by(AuditLog.occurred_at, AuditLog.id)).all()
