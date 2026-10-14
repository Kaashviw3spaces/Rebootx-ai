"""Transactional, tenant-scoped mock steps; safe to repeat after lost activity ACKs."""
from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy import select

from app.models.entities import AuditLog, Incident, IncidentDiagnosis, Integration, RecoveryAttempt, Workflow, utcnow
from app.temporal.schemas import StepRequest, StepResult


class RecoveryDenied(Exception):
    """Fixed-code rejection, suitable for a non-retryable Temporal failure."""


@dataclass(frozen=True)
class MockFixture:
    category: str
    retry_success: bool = False
    fallback_success: bool = False
    verification_success: bool = True


FIXTURES = {
    'TRANSIENT_NETWORK_FAILURE': MockFixture('TRANSIENT_NETWORK_FAILURE', True),
    'NETWORK_RETRY_SUCCESS': MockFixture('TRANSIENT_NETWORK_FAILURE', True),
    'PROVIDER_UNAVAILABLE': MockFixture('TRANSIENT_NETWORK_FAILURE', False, True),
    'NETWORK_FALLBACK_SUCCESS': MockFixture('TRANSIENT_NETWORK_FAILURE', False, True),
    'NETWORK_BOTH_FAIL': MockFixture('TRANSIENT_NETWORK_FAILURE'),
    'NETWORK_VERIFY_FAIL': MockFixture('TRANSIENT_NETWORK_FAILURE', True, False, False),
    'RATE_LIMIT': MockFixture('RATE_LIMIT', True),
    'AUTHENTICATION_FAILURE': MockFixture('AUTHENTICATION_FAILURE'),
    'INVALID_PAYLOAD': MockFixture('INVALID_PAYLOAD'),
}
RECOVERABLE = {'TRANSIENT_NETWORK_FAILURE', 'RATE_LIMIT'}
ESCALATION_REASONS = {'AUTHENTICATION_FAILURE', 'INVALID_PAYLOAD', 'UNKNOWN_FAILURE',
                      'MOCK_ACTIONS_EXHAUSTED', 'MOCK_VERIFICATION_FAILED', 'ACTIVITY_FAILURE'}


def scoped_incident(db, request: StepRequest, *, lock=True):
    data = request.recovery
    if data.version != 1 or request.operation not in {'accept', 'diagnose', 'plan', 'retry', 'fallback', 'verify', 'recover', 'escalate'}:
        raise RecoveryDenied('INVALID_RECOVERY_REQUEST')
    try:
        incident_id, tenant_id, workflow_id, integration_id = map(UUID, (
            data.incident_id, data.tenant_id, data.workflow_id, data.integration_id))
    except (ValueError, TypeError):
        raise RecoveryDenied('INVALID_RECOVERY_REQUEST') from None
    query = select(Incident).where(
        Incident.id == incident_id, Incident.tenant_id == tenant_id,
        Incident.workflow_id == workflow_id, Incident.integration_id == integration_id,
    )
    incident = db.scalar(query.with_for_update() if lock else query)
    integration = db.scalar(select(Integration).where(
        Integration.id == integration_id, Integration.tenant_id == tenant_id, Integration.enabled.is_(True)))
    registered = db.scalar(select(Workflow).where(
        Workflow.id == workflow_id, Workflow.tenant_id == tenant_id,
        Workflow.integration_id == integration_id, Workflow.enabled.is_(True)))
    if incident is None or integration is None or registered is None:
        raise RecoveryDenied('RECOVERY_SCOPE_DENIED')
    return incident


def apply_step(db, request: StepRequest, diagnosis_outcome=None, ai_settings=None) -> StepResult:
    incident = scoped_incident(db, request)
    tenant_id, incident_id = incident.tenant_id, incident.id
    operation = request.operation
    key = 'recovery:v1:' + operation
    prior = db.scalar(select(AuditLog).where(
        AuditLog.tenant_id == tenant_id, AuditLog.incident_id == incident_id, AuditLog.logical_key == key))
    if prior is not None:
        return StepResult(**prior.redacted_details['result'])
    fixture = FIXTURES.get(incident.failure_type, MockFixture('UNKNOWN_FAILURE'))
    category = fixture.category
    diagnosis_record = db.scalar(select(IncidentDiagnosis).where(
        IncidentDiagnosis.tenant_id == tenant_id, IncidentDiagnosis.incident_id == incident_id))
    if diagnosis_record is not None:
        category = diagnosis_record.recovery_category
    target, success, reason, delay = incident.status, False, '', 0
    attempts = db.scalars(select(RecoveryAttempt).where(
        RecoveryAttempt.tenant_id == tenant_id, RecoveryAttempt.incident_id == incident_id)).all()
    expected_states = {
        'accept': {'RECEIVED'}, 'diagnose': {'VALIDATING'}, 'plan': {'DIAGNOSING'},
        'retry': {'PLANNED'}, 'fallback': {'EXECUTING'}, 'verify': {'EXECUTING'},
        'recover': {'VERIFYING'}, 'escalate': {'RECEIVED', 'VALIDATING', 'DIAGNOSING', 'PLANNED', 'EXECUTING', 'VERIFYING'},
    }
    if incident.status not in expected_states[operation]:
        raise RecoveryDenied('INVALID_RECOVERY_TRANSITION')
    if operation == 'accept':
        target = 'VALIDATING'
    elif operation == 'diagnose':
        if diagnosis_outcome is not None:
            output = diagnosis_outcome.diagnosis
            decision = diagnosis_outcome.policy
            # Legacy mock/fallback fixtures preserve Checkpoint 2 behavior.
            category = fixture.category if diagnosis_outcome.status in {'MOCK', 'FALLBACK'} else decision.recovery_category
            diagnosis_record = IncidentDiagnosis(
                tenant_id=tenant_id, incident_id=incident_id, status=diagnosis_outcome.status,
                **output.model_dump(), provider=diagnosis_outcome.source,
                model_id=diagnosis_outcome.model_id, requested_model_id=ai_settings.ai_model,
                fallback_reason=diagnosis_outcome.fallback_reason, policy_reason=decision.reason,
                recovery_category=category, allow_fallback=decision.allow_fallback,
            )
            db.add(diagnosis_record)
        target = 'DIAGNOSING'
        delay = 2 if category == 'RATE_LIMIT' else 0
    elif operation == 'plan':
        if category not in RECOVERABLE:
            raise RecoveryDenied('UNSAFE_RECOVERY_BLOCKED')
        target = 'PLANNED'
    elif operation in {'retry', 'fallback'}:
        if category not in RECOVERABLE:
            raise RecoveryDenied('UNSAFE_RECOVERY_BLOCKED')
        if (operation == 'fallback' and diagnosis_record is not None
                and diagnosis_record.status == 'SUCCEEDED' and not diagnosis_record.allow_fallback):
            raise RecoveryDenied('UNSAFE_RECOVERY_BLOCKED')
        if operation == 'fallback' and not any(a.logical_key == 'recovery:v1:retry' and a.outcome == 'FAILED' for a in attempts):
            raise RecoveryDenied('INVALID_RECOVERY_TRANSITION')
        target = 'EXECUTING'
        success = fixture.retry_success if operation == 'retry' else fixture.fallback_success
        if diagnosis_record is not None and diagnosis_record.status == 'SUCCEEDED':
            if incident.failure_type not in FIXTURES:
                success = True  # Synthetic adapter only, never a provider completion claim.
            if operation == 'retry' and diagnosis_record.recommended_action == 'USE_APPROVED_FALLBACK':
                success = False
        reason = '' if success else 'MOCK_' + operation.upper() + '_FAILED'
        now = utcnow()
        db.add(RecoveryAttempt(
            tenant_id=tenant_id, incident_id=incident_id, logical_key=key,
            action='MOCK_' + operation.upper(), adapter='mock-only-v1',
            outcome='SUCCEEDED' if success else 'FAILED', failure_reason=reason or None,
            external_reference='mock:' + str(incident_id) + ':' + operation if success else None,
            started_at=now, ended_at=now,
        ))
    elif operation == 'verify':
        target = 'VERIFYING'
        success = fixture.verification_success and any(a.outcome == 'SUCCEEDED' and a.adapter == 'mock-only-v1' for a in attempts)
        incident.verification_outcome = 'MOCK_VERIFIED' if success else 'MOCK_FAILED'
        reason = '' if success else 'MOCK_VERIFICATION_FAILED'
    elif operation == 'recover':
        if incident.verification_outcome != 'MOCK_VERIFIED':
            raise RecoveryDenied('UNVERIFIED_RECOVERY_BLOCKED')
        target, success = 'RECOVERED', True
        incident.resolved_at = utcnow()
    else:
        if request.reason not in ESCALATION_REASONS:
            raise RecoveryDenied('INVALID_ESCALATION_REASON')
        target, reason = 'NEEDS_ATTENTION', request.reason
        incident.recovery_reason = reason
        now = utcnow()
        db.add(RecoveryAttempt(
            tenant_id=tenant_id, incident_id=incident_id, logical_key=key, action='ESCALATE',
            adapter='mock-only-v1', outcome='ESCALATED', failure_reason=reason,
            started_at=now, ended_at=now,
        ))
    incident.status = target
    result = StepResult(target, category, success, reason, delay)
    details = {'mode': 'mock-only', 'result': asdict(result)}
    if operation == 'diagnose' and diagnosis_record is not None:
        details['diagnosis'] = {'status': diagnosis_record.status, 'model_id': diagnosis_record.model_id,
                                'source': diagnosis_record.source,
                                'policy_reason': diagnosis_record.policy_reason,
                                'fallback_reason': diagnosis_record.fallback_reason}
        if diagnosis_outcome is not None and diagnosis_outcome.validation_codes:
            details['diagnosis']['validation_codes'] = list(diagnosis_outcome.validation_codes)
            details['diagnosis']['validation_fields'] = list(diagnosis_outcome.validation_fields)
    db.add(AuditLog(
        tenant_id=tenant_id, incident_id=incident_id, actor='temporal:mock-recovery-v1',
        logical_key=key, event_type='RECOVERY_' + operation.upper(),
        redacted_details=details,
    ))
    db.flush()
    return result
