"""Durable reservation before POST; uncertain actions are never automatically resent."""
from dataclasses import asdict
import hashlib
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.integrations.n8n.client import N8nClient, N8nError
from app.models.entities import AuditLog, IncidentDiagnosis, Integration, RecoveryAttempt, Workflow, utcnow
from app.services.recovery import RecoveryDenied, scoped_incident, RECOVERABLE
from app.temporal.schemas import StepResult


def lock(db):
    if db.bind.dialect.name == 'sqlite':
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')


def authorized(db, incident, settings):
    if settings.recovery_mode != 'real_n8n' or incident.recovery_mode != 'real_n8n':
        raise N8nError('N8N_MODE_MISMATCH')
    workflow = db.get(Workflow, incident.workflow_id)
    integration = db.get(Integration, incident.integration_id)
    if integration.kind != 'n8n' or incident.source != 'n8n':
        raise N8nError('N8N_PROVIDER_NOT_AUTHORIZED')
    matches = [a for a in settings.n8n_authorizations if a.tenant_id == incident.tenant_id
               and a.integration_id == incident.integration_id and a.workflow_external_id == workflow.external_id]
    if len(matches) != 1:
        raise N8nError('N8N_WORKFLOW_NOT_AUTHORIZED')
    auth = matches[0]
    if auth.operation != 'retry_execution':
        raise N8nError('N8N_UNSUPPORTED_OPERATION')
    # First integration deliberately restricted to controlled, side-effect-free demonstrations.
    if workflow.kind != 'side_effect_safe_demo_v1' or not auth.idempotent or not auth.side_effect_safe:
        raise N8nError('N8N_NON_IDEMPOTENT_OR_UNSAFE')
    diagnosis = db.scalar(select(IncidentDiagnosis).where(
        IncidentDiagnosis.tenant_id == incident.tenant_id, IncidentDiagnosis.incident_id == incident.id))
    safe_codes = {'NETWORK_RETRY_SUCCESS', 'TRANSIENT_NETWORK_FAILURE', 'NETWORK_ERROR', 'TIMEOUT',
                  'SERVICE_UNAVAILABLE', 'PROVIDER_UNAVAILABLE', 'RATE_LIMIT'}
    if (incident.failure_type not in safe_codes or diagnosis is None or diagnosis.recovery_category not in RECOVERABLE
            or diagnosis.requires_human_approval or diagnosis.status == 'POLICY_REJECTED'):
        raise N8nError('N8N_POLICY_DENIED')
    return workflow.external_id, auth.workflow_sha256


def attempt_for(db, incident):
    return db.scalar(select(RecoveryAttempt).where(RecoveryAttempt.tenant_id == incident.tenant_id,
        RecoveryAttempt.incident_id == incident.id, RecoveryAttempt.logical_key == 'recovery:v1:retry'))


def record(db, incident, request, success=False, reason=''):
    result = StepResult(incident.status, success=success, reason=reason, mode='real_n8n')
    attempt = attempt_for(db, incident)
    db.add(AuditLog(tenant_id=incident.tenant_id, incident_id=incident.id,
        actor='temporal:real-n8n-v1', logical_key='recovery:v1:' + request.operation,
        event_type='RECOVERY_' + request.operation.upper(), redacted_details={
            'mode': 'real_n8n', 'result': asdict(result), 'verification_outcome': incident.verification_outcome,
            'evidence': dict(attempt.evidence) if attempt and attempt.evidence else None}))
    return result


def fail(db, incident, request, reason, *, failed=False):
    incident.status = 'NEEDS_ATTENTION'
    incident.recovery_reason = reason
    incident.verification_outcome = 'REAL_RECOVERY_FAILED' if failed else 'REAL_RECOVERY_UNVERIFIED'
    attempt = attempt_for(db, incident)
    if attempt:
        attempt.outcome = 'FAILED' if failed else 'UNVERIFIED'
        attempt.failure_reason, attempt.ended_at = reason, utcnow()
    return record(db, incident, request, reason=reason)


def real_step(sessions, request, settings, client_factory=N8nClient):
    operation = request.operation
    key = 'recovery:v1:' + operation
    with sessions.begin() as db:
        lock(db)
        incident = scoped_incident(db, request)
        prior = db.scalar(select(AuditLog).where(AuditLog.tenant_id == incident.tenant_id,
            AuditLog.incident_id == incident.id, AuditLog.logical_key == key))
        if prior:
            return StepResult(**prior.redacted_details['result'])
        if incident.status == 'NEEDS_ATTENTION':
            return StepResult(incident.status, reason=incident.recovery_reason or '')
        if operation == 'escalate':
            return fail(db, incident, request, 'N8N_RECOVERY_ESCALATED')
        expected = {'retry': 'PLANNED', 'verify': 'EXECUTING', 'recover': 'VERIFYING'}
        if operation not in expected or incident.status != expected[operation]:
            raise RecoveryDenied('INVALID_RECOVERY_TRANSITION')
        try:
            workflow_id, fingerprint = authorized(db, incident, settings)
        except N8nError as exc:
            return fail(db, incident, request, str(exc))
        attempt = attempt_for(db, incident)
        if operation == 'recover':
            if (incident.verification_outcome != 'REAL_RECOVERY_VERIFIED' or not attempt
                    or not attempt.evidence or attempt.evidence.get('external_status') != 'success'
                    or not attempt.evidence.get('verified_at')):
                return fail(db, incident, request, 'N8N_UNVERIFIED_RECOVERY_BLOCKED')
            incident.status, incident.resolved_at = 'RECOVERED', utcnow()
            return record(db, incident, request, True)
        if operation == 'retry':
            if attempt:
                return fail(db, incident, request, 'N8N_ACTION_COMPLETION_UNKNOWN')
            # Persist before any network request. Uniqueness spans incidents/failed steps.
            action_key = hashlib.sha256(f'{incident.tenant_id}:{incident.integration_id}:{incident.source_execution_id}'.encode()).hexdigest()
            if db.scalar(select(RecoveryAttempt.id).where(RecoveryAttempt.external_action_key == action_key)):
                return fail(db, incident, request, 'N8N_DUPLICATE_EXTERNAL_ACTION')
            attempt = RecoveryAttempt(tenant_id=incident.tenant_id, incident_id=incident.id,
                logical_key='recovery:v1:retry', action='RETRY_EXECUTION', adapter='n8n-public-api-v1',
                outcome='RESERVED', external_action_key=action_key,
                evidence={'tenant_id': str(incident.tenant_id), 'integration_id': str(incident.integration_id),
                    'workflow_id': workflow_id, 'original_execution_id': incident.source_execution_id,
                    'operation': 'retry_execution', 'verification_method': 'GET /api/v1/executions/{id}',
                    'reserved_at': utcnow().isoformat()})
            db.add(attempt)
            try:
                db.flush()
            except IntegrityError:
                # Another incident won the cross-incident reservation. Temporal redelivery will see it.
                raise RecoveryDenied('N8N_DUPLICATE_EXTERNAL_ACTION') from None
        elif not attempt or not attempt.external_reference:
            return fail(db, incident, request, 'N8N_MISSING_RESULT_EXECUTION')
        original_id = incident.source_execution_id
        resulting_id = attempt.external_reference
        attempt_id = attempt.id

    error, external_status, resulting = None, None, None
    client = None
    try:
        client = client_factory(settings)
        if operation == 'retry':
            original = client.inspect(original_id, workflow_id, fingerprint=fingerprint)
            if original.status != 'error' or original.retryOf is not None or original.retrySuccessId is not None:
                raise N8nError('N8N_ORIGINAL_NOT_RETRYABLE')
            resulting = client.retry(original_id, workflow_id)
            resulting_id = resulting.id
        else:
            deadline = time.monotonic() + settings.n8n_verification_seconds
            # Both time and count bounded, including when tests replace the monotonic clock.
            for _ in range(20):
                resulting = client.inspect(resulting_id, workflow_id, retry_of=original_id)
                external_status = resulting.status
                if external_status in {'success', 'error', 'canceled', 'crashed'}:
                    break
                if time.monotonic() >= deadline:
                    raise N8nError('N8N_VERIFICATION_TIMEOUT')
                time.sleep(min(0.5, max(0, deadline - time.monotonic())))
            else:
                raise N8nError('N8N_VERIFICATION_TIMEOUT')
    except N8nError as exc:
        error = str(exc)
    finally:
        if client:
            client.close()

    with sessions.begin() as db:
        lock(db)
        incident = scoped_incident(db, request)
        attempt = db.get(RecoveryAttempt, attempt_id)
        # A concurrent redelivery may already have escalated the uncertain reservation.
        if incident.status == 'NEEDS_ATTENTION':
            if resulting_id:
                attempt.external_reference = resulting_id
                attempt.evidence = {**attempt.evidence, 'resulting_execution_id': resulting_id,
                    'late_observation_at': utcnow().isoformat()}
            return StepResult(incident.status, reason=incident.recovery_reason or '')
        evidence = dict(attempt.evidence)
        attempt.ended_at = utcnow()
        if error:
            attempt.outcome, attempt.failure_reason = 'UNVERIFIED', error
            evidence['failure_reason'] = error
            evidence['last_checked_at'] = utcnow().isoformat()
            attempt.evidence = evidence
            return fail(db, incident, request, error)
        if operation == 'retry':
            attempt.external_reference, attempt.outcome = resulting_id, 'ACTION_ACCEPTED'
            evidence.update(resulting_execution_id=resulting_id, recovered_at=utcnow().isoformat())
            attempt.evidence = evidence
            incident.status = 'EXECUTING'
            return record(db, incident, request, True)
        evidence.update(external_status=external_status, verified_at=utcnow().isoformat())
        attempt.evidence = evidence
        if external_status != 'success':
            attempt.outcome, attempt.failure_reason = 'FAILED', 'N8N_EXECUTION_FAILED'
            return fail(db, incident, request, 'N8N_EXECUTION_FAILED', failed=True)
        attempt.outcome = 'VERIFIED'
        incident.status, incident.verification_outcome = 'VERIFYING', 'REAL_RECOVERY_VERIFIED'
        return record(db, incident, request, True)
