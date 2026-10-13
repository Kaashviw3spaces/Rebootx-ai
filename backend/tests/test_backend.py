import hashlib
import hmac
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.database import make_engine, session_factory
from app.core.security import token_hash
from app.main import create_app
from app.models.entities import AuditLog, Incident, Integration, Tenant, Workflow



def payload(**changes):
    data = {
        'schema_version': '1.0', 'event_id': 'evt-1',
        'timestamp': datetime.now(timezone.utc).isoformat(), 'source': 'n8n',
        'source_execution_id': 'exec-1', 'workflow_external_id': 'notify-orders',
        'failed_step': 'send_confirmation', 'operation_id': 'notify-order-1',
        'error': {'category': 'PROVIDER_UNAVAILABLE', 'message': 'secret-token customer@example.com HTTP 503'},
    }
    data.update(changes)
    return data


def send(context, data=None, tenant=0, raw=None, signature=None):
    client, _, ids, _, _, _ = context
    raw = raw if raw is not None else json.dumps(data or payload()).encode()
    digest = hmac.new(os.environ[f'TEST_WEBHOOK_{tenant}'].encode(), raw, hashlib.sha256).hexdigest()
    return client.post('/api/v1/events/failure', content=raw, headers={
        'Content-Type': 'application/json', 'X-Integration-ID': ids[tenant],
        'X-Webhook-Signature': signature or 'sha256=' + digest,
    })


def test_health(context):
    assert context[0].get('/health').json() == {'status': 'ok'}


def test_valid_signature_persistence_and_redaction(context):
    response = send(context)
    assert response.status_code == 202
    assert response.json()['status'] == 'RECEIVED'
    assert response.json()['duplicate'] is False
    result = context[0].get('/api/v1/incidents/' + response.json()['incident_id'], headers={'Authorization': 'Bearer ' + context[3][0]})
    assert result.status_code == 200
    assert result.json()['error_details']['message'] == '[REDACTED]'
    assert 'secret-token' not in result.text
    with context[1]() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 1
        audit = db.scalar(select(AuditLog))
        assert audit.event_type == 'INCIDENT_RECEIVED'
        assert 'secret-token' not in json.dumps(audit.redacted_details)


@pytest.mark.parametrize('signature', ['sha256=' + '0' * 64, 'invalid'])
def test_invalid_signature(context, signature):
    assert send(context, signature=signature).status_code == 401
    with context[1]() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 0


def test_signature_over_exact_bytes(context):
    raw = json.dumps(payload()).encode()
    signature = 'sha256=' + hmac.new(os.environ['TEST_WEBHOOK_0'].encode(), raw, hashlib.sha256).hexdigest()
    assert send(context, raw=raw + b' ', signature=signature).status_code == 401
    assert send(context, raw=raw, signature=signature).status_code == 202


@pytest.mark.parametrize('seconds', [-301, 301])
def test_timestamp_outside_tolerance(context, seconds):
    timestamp = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
    assert send(context, payload(timestamp=timestamp)).status_code == 401


def test_duplicate_event_and_execution_key(context):
    event = payload()
    first = send(context, event).json()
    second = send(context, event).json()
    third = send(context, {**event, 'event_id': 'different-id'}).json()
    assert first['incident_id'] == second['incident_id'] == third['incident_id']
    assert second['duplicate'] and third['duplicate']
    with context[1]() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_tenant_isolation(context):
    first = send(context).json()['incident_id']
    second = send(context, tenant=1).json()['incident_id']
    assert first != second  # event IDs are unique within a tenant, not globally.
    path = '/api/v1/incidents/' + first
    assert context[0].get(path, headers={'Authorization': 'Bearer ' + context[3][1]}).status_code == 404
    assert context[0].get(path).status_code == 401
    assert context[0].get(path, headers={'Authorization': 'Bearer ' + 'z' * 32}).status_code == 401
    assert context[0].get(path, headers={'Authorization': 'Bearer ' + context[3][0]}).status_code == 200


@pytest.mark.parametrize('change', [
    {'tenant_id': 'attacker'}, {'timestamp': 'bad'}, {'timestamp': '2026-10-13T00:00:00'},
    {'event_id': ''}, {'error': {'category': 'BAD', 'message': 'secret', 'token': 'secret'}},
    {'source': 'unsupported'}, {'context': {'recipient': 'private'}},
])
def test_malformed_event(context, change):
    response = send(context, payload(**change))
    assert response.status_code == 422
    assert response.json() == {'detail': 'Malformed failure event'}


def test_invalid_json(context):
    assert send(context, raw=b'{invalid secret').status_code == 422


def test_unknown_or_disabled_integration(context):
    with context[1]() as db:
        integration = db.get(Integration, UUID(context[2][0]))
        integration.enabled = False
        db.commit()
    assert send(context).status_code == 401
    assert context[0].post('/api/v1/events/failure', content=b'{}').status_code == 401


def test_workflow_must_be_registered_to_authenticated_integration(context):
    assert send(context, payload(workflow_external_id='unknown')).status_code == 404
    with context[1]() as db:
        workflow = db.scalar(select(Workflow).where(Workflow.integration_id == UUID(context[2][0])))
        workflow.enabled = False
        db.commit()
    assert send(context).status_code == 404


def test_body_size_limit(context):
    assert send(context, raw=b'x' * 65537).status_code == 413


def test_missing_secret_is_not_persisted(context, monkeypatch):
    monkeypatch.delenv('TEST_WEBHOOK_0')
    response = context[0].post('/api/v1/events/failure', content=b'{}', headers={
        'Content-Type': 'application/json', 'X-Integration-ID': context[2][0], 'X-Webhook-Signature': 'sha256=' + 'a' * 64,
    })
    assert response.status_code == 503


def test_concurrent_duplicate_deliveries(context):
    event = payload()
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: send(context, event), range(4)))
    assert all(response.status_code == 202 for response in responses)
    assert len({response.json()['incident_id'] for response in responses}) == 1
    with context[1]() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_cross_tenant_foreign_key_is_rejected(context):
    with context[1]() as db:
        integrations = db.scalars(select(Integration).order_by(Integration.secret_ref)).all()
        db.add(Workflow(tenant_id=integrations[0].tenant_id, integration_id=integrations[1].id, external_id='cross-tenant'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_migration_matches_models_and_downgrades(context):
    config = context[5]
    for operation, revision in [(command.check, None), (command.downgrade, 'base'), (command.upgrade, 'head')]:
        with context[4].begin() as connection:
            config.attributes['connection'] = connection
            operation(config) if revision is None else operation(config, revision)
        tables = set(inspect(context[4]).get_table_names())
        if revision == 'base':
            assert 'incidents' not in tables
        elif revision == 'head':
            assert tables >= {'tenants', 'integrations', 'workflows', 'incidents', 'recovery_attempts', 'audit_logs'}


def test_secret_reference_reads_dotenv(tmp_path, monkeypatch):
    from app.core.security import resolve_secret
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('LOCAL_SECRET', raising=False)
    (tmp_path / '.env').write_text('LOCAL_SECRET=' + 'synthetic-secret-' + 'a' * 32)
    assert resolve_secret('LOCAL_SECRET') == 'synthetic-secret-' + 'a' * 32
    monkeypatch.setenv('LOCAL_SECRET', 'environment-override-' + 'b' * 32)
    assert resolve_secret('LOCAL_SECRET') == 'environment-override-' + 'b' * 32


def test_integration_credentials_cannot_be_swapped(context):
    raw = json.dumps(payload()).encode()
    signature = 'sha256=' + hmac.new(os.environ['TEST_WEBHOOK_0'].encode(), raw, hashlib.sha256).hexdigest()
    assert send(context, raw=raw, signature=signature, tenant=1).status_code == 401


def test_audit_failure_rolls_back_incident(context):
    from sqlalchemy import event
    sessions = context[0].app.state.sessions

    def fail_audit(session, _, __):
        if any(isinstance(item, AuditLog) for item in session.new):
            raise RuntimeError('Synthetic audit persistence failure')

    event.listen(sessions, 'before_flush', fail_audit)
    try:
        with pytest.raises(RuntimeError, match='Synthetic audit persistence failure'):
            send(context)
    finally:
        event.remove(sessions, 'before_flush', fail_audit)
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 0
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 0
