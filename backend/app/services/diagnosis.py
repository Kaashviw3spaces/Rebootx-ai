"""Read sanitized evidence before inference; no database transaction spans an AI call."""
from datetime import timezone

from sqlalchemy import select

from app.ai.schemas import DiagnosisInput
from app.models.entities import AuditLog, Integration, RecoveryAttempt, Workflow
from app.services.recovery import RecoveryDenied, scoped_incident


def diagnosis_evidence(sessions, request):
    with sessions() as db:
        incident = scoped_incident(db, request, lock=False)
        prior = db.scalar(select(AuditLog).where(
            AuditLog.tenant_id == incident.tenant_id, AuditLog.incident_id == incident.id,
            AuditLog.logical_key == 'recovery:v1:diagnose'))
        if prior is not None:
            return None
        if incident.status != 'VALIDATING':
            raise RecoveryDenied('INVALID_RECOVERY_TRANSITION')
        integration = db.get(Integration, incident.integration_id)
        registered = db.get(Workflow, incident.workflow_id)
        when = incident.event_timestamp
        if when.tzinfo is None:  # SQLite drops timezone information.
            when = when.replace(tzinfo=timezone.utc)
        status = incident.error_details.get('http_status')
        if type(status) is not int or not 100 <= status <= 599:
            status = None
        attempts = db.scalars(select(RecoveryAttempt).where(
            RecoveryAttempt.tenant_id == incident.tenant_id, RecoveryAttempt.incident_id == incident.id,
        ).order_by(RecoveryAttempt.started_at, RecoveryAttempt.id).limit(10)).all()
        codes = []
        for attempt in attempts:
            if attempt.action in {'MOCK_RETRY', 'MOCK_FALLBACK'} and attempt.outcome in {'SUCCEEDED', 'FAILED'}:
                codes.append(attempt.action + '_' + attempt.outcome)
            elif attempt.action == 'ESCALATE':
                codes.append('ESCALATED')
        return DiagnosisInput(failure_code=incident.failure_type, failure_timestamp=when,
                              integration_type='n8n' if integration.kind == 'n8n' else 'unknown',
                              workflow_kind='notification_v1' if registered.kind == 'notification_v1' else 'unknown',
                              http_status=status, previous_attempts=codes)
