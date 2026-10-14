"""Runs on disposable SQLite databases or isolated PostgreSQL fixture schemas."""
from uuid import UUID

import pytest
from sqlalchemy import func, select
from temporalio.testing import ActivityEnvironment

from app.ai.diagnosis import DiagnosisEngine
from app.ai.schemas import Diagnosis
from app.models.entities import AuditLog, Incident, IncidentDiagnosis, RecoveryAttempt, RecoveryOutbox
from app.temporal.activities import RecoveryActivities
from app.temporal.schemas import StepRequest
from test_ai import FakeProvider, settings
from test_fast_path import new_failure


@pytest.mark.parametrize('source,code,http_status', [
    ('deterministic', 'UNKNOWN_FAILURE', 429),
    ('gemma', 'UNKNOWN_FAILURE', 500),
    ('mock', 'NETWORK_RETRY_SUCCESS', None),
])
def test_checkpoint3_sources_and_linked_recovery_persist_in_isolated_database(context, source, code, http_status):
    # Gemma transport is mocked: this validates database provenance, not live inference.
    config = settings(ai_provider='mock' if source == 'mock' else 'gemma', ai_fast_path_enabled=True)
    provider = FakeProvider()
    activities = RecoveryActivities(context[1], config, DiagnosisEngine(config, provider))
    data = new_failure(context, code, http_status)
    env = ActivityEnvironment()
    for operation in ['accept', 'diagnose', 'plan', 'retry', 'verify', 'recover']:
        env.run(activities.step, StepRequest(data, operation))
    env.run(activities.step, StepRequest(data, 'diagnose'))
    assert len(provider.calls) == (1 if source == 'gemma' else 0)
    with context[1]() as db:
        incident = db.get(Incident, UUID(data.incident_id))
        diagnosis = db.scalar(select(IncidentDiagnosis).where(IncidentDiagnosis.incident_id == incident.id))
        assert diagnosis.provider == diagnosis.source == source
        assert diagnosis.tenant_id == incident.tenant_id == UUID(data.tenant_id)
        assert diagnosis.incident_id == incident.id and diagnosis.diagnosed_at is not None
        assert db.scalar(select(func.count()).select_from(IncidentDiagnosis)) == 1
        Diagnosis.model_validate({name: getattr(diagnosis, name) for name in Diagnosis.model_fields})
        attempt = db.scalar(select(RecoveryAttempt))
        outbox = db.scalar(select(RecoveryOutbox))
        assert attempt.tenant_id == outbox.tenant_id == incident.tenant_id
        assert attempt.incident_id == outbox.incident_id == diagnosis.incident_id
        assert incident.status == 'RECOVERED' and incident.verification_outcome == 'MOCK_VERIFIED'
        audit = db.scalar(select(AuditLog).where(AuditLog.logical_key == 'recovery:v1:diagnose'))
        assert audit.tenant_id == diagnosis.tenant_id and audit.incident_id == diagnosis.incident_id
        assert audit.redacted_details['diagnosis']['source'] == source
    client, _, _, tokens, _, _ = context
    path = f'/api/v1/incidents/{data.incident_id}/recovery'
    assert client.get(path, headers={'Authorization': 'Bearer ' + tokens[1]}).status_code == 404
    response = client.get(path, headers={'Authorization': 'Bearer ' + tokens[0]})
    assert response.status_code == 200 and response.json()['diagnosis']['source'] == source
