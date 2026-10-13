"""Transactional, tenant-scoped mock steps; safe to repeat after lost activity ACKs."""
from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy import select

from app.models.entities import AuditLog, Incident, Integration, RecoveryAttempt, Workflow, utcnow
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


def apply_step(db, request: StepRequest) -> StepResult:
    data = request.recovery
    if data.version != 1 or request.operation not in {'accept', 'diagnose', 'plan', 'retry', 'fallback', 'verify', 'recover', 'escalate'}:
        raise RecoveryDenied('INVALID_RECOVERY_REQUEST')
    try:
        incident_id, tenant_id, workflow_id, integration_id = map(UUID, (
            data.incident_id, data.tenant_id, data.workflow_id, data.integration_id))
    except (ValueError, TypeError):
        raise RecoveryDenied('INVALID_RECOVERY_REQUEST') from None
    incident = db.scalar(select(Incident).where(
        Incident.id == incident_id, Incident.tenant_id == tenant_id,
        Incident.workflow_id == workflow_id, Incident.integration_id == integration_id,
    ).with_for_update())
    integration = db.scalar(select(Integration).where(
        Integration.id == integration_id, Integration.tenant_id == tenant_id, Integration.enabled.is_(True)))
    registered = db.scalar(select(Workflow).where(
        Workflow.id == workflow_id, Workflow.tenant_id == tenant_id,
        Workflow.integration_id == integration_id, Workflow.enabled.is_(True)))
    if incident is None or integration is None or registered is None:
        raise RecoveryDenied('RECOVERY_SCOPE_DENIED')
    operation = request.operation
    key = 'recovery:v1:' + operation
    prior = db.scalar(select(AuditLog).where(
        AuditLog.tenant_id == tenant_id, AuditLog.incident_id == incident_id, AuditLog.logical_key == key))
    if prior is not None:
        return StepResult(**prior.redacted_details['result'])
    fixture = FIXTURES.get(incident.failure_type, MockFixture('UNKNOWN_FAILURE'))
    category = fixture.category
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
        target = 'DIAGNOSING'
        delay = 2 if category == 'RATE_LIMIT' else 0
    elif operation == 'plan':
        if category not in RECOVERABLE:
            raise RecoveryDenied('UNSAFE_RECOVERY_BLOCKED')
        target = 'PLANNED'
    elif operation in {'retry', 'fallback'}:
        if category not in RECOVERABLE:
            raise RecoveryDenied('UNSAFE_RECOVERY_BLOCKED')
        if operation == 'fallback' and not any(a.logical_key == 'recovery:v1:retry' and a.outcome == 'FAILED' for a in attempts):
            raise RecoveryDenied('INVALID_RECOVERY_TRANSITION')
        target = 'EXECUTING'
        success = fixture.retry_success if operation == 'retry' else fixture.fallback_success
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
    db.add(AuditLog(
        tenant_id=tenant_id, incident_id=incident_id, actor='temporal:mock-recovery-v1',
        logical_key=key, event_type='RECOVERY_' + operation.upper(),
        redacted_details={'mode': 'mock-only', 'result': asdict(result)},
    ))
    db.flush()
    return result
