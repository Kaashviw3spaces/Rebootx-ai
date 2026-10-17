"""Deterministic HTTP fixtures; no customer workflows or production credentials."""
import asyncio
from dataclasses import replace
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from app.core.config import Settings, N8nAuthorization
from app.integrations.n8n.client import N8nClient, N8nError, workflow_fingerprint
from app.models.entities import AuditLog, Incident, RecoveryAttempt, Workflow
from app.temporal.activities import RecoveryActivities
from app.temporal.schemas import StepRequest
from app.temporal.workflows import IncidentRecoveryWorkflow
from test_recovery import create_incident
from test_backend import payload, send

SNAPSHOT = {'id': 'notify-orders', 'nodes': [], 'settings': {}}


def setup(context, **overrides):
    data = create_incident(context)
    with context[1].begin() as db:
        incident = db.get(Incident, UUID(data.incident_id))
        incident.recovery_mode = 'real_n8n'
        incident.source_execution_id = '101'
        db.get(Workflow, incident.workflow_id).kind = 'side_effect_safe_demo_v1'
    auth = N8nAuthorization(tenant_id=data.tenant_id, integration_id=data.integration_id,
        workflow_external_id='notify-orders', idempotent=True, side_effect_safe=True,
        workflow_sha256=workflow_fingerprint(SNAPSHOT))
    config = Settings(_env_file=None, database_url='sqlite:///:memory:', ai_provider='mock',
        recovery_mode='real_n8n', n8n_api_key='synthetic-private-key', n8n_supported_version='2.43.6',
        n8n_authorizations=[auth], n8n_verification_seconds=0, **overrides)
    return data, config


def execution(id='102', status='success', workflow='notify-orders', retry='101'):
    return dict(id=id, workflowId=workflow, status=status, retryOf=retry)


def activities(context, config, handler):
    return RecoveryActivities(context[1], config,
        n8n_client_factory=lambda s: N8nClient(s, httpx.MockTransport(handler)))


def prepare(acts, data):
    for op in ['accept', 'diagnose', 'plan']:
        ActivityEnvironment().run(acts.step, StepRequest(data, op))


def run(acts, data, op):
    return ActivityEnvironment().run(acts.step, StepRequest(data, op))


def normal_handler(calls, *, action_status=200, verify_status='success'):
    def handler(req):
        calls.append((req.method, req.url.path))
        assert req.headers['X-N8N-API-KEY'] == 'synthetic-private-key'
        if req.method == 'POST':
            assert req.content == b'{"loadWorkflow":false}'
            return httpx.Response(action_status, json=execution())
        if req.url.path.endswith('/101'):
            return httpx.Response(200, json={**execution('101', 'error', retry=None), 'workflowData': SNAPSHOT})
        return httpx.Response(200, json=execution(status=verify_status))
    return handler


def test_verified_real_recovery_audit_api_and_redelivery(context):
    data, config = setup(context)
    calls = []
    acts = activities(context, config, normal_handler(calls))
    prepare(acts, data)
    for op in ['retry', 'verify', 'recover']:
        first = run(acts, data, op)
        assert first.success
        assert run(acts, data, op) == first
    assert [m for m, _ in calls].count('POST') == 1
    assert calls[-1] == ('GET', '/api/v1/executions/102')
    with context[1]() as db:
        incident = db.get(Incident, UUID(data.incident_id))
        assert incident.status == 'RECOVERED'
        assert incident.verification_outcome == 'REAL_RECOVERY_VERIFIED'
        attempt = db.scalar(select(RecoveryAttempt))
        assert attempt.outcome == 'VERIFIED'
        assert attempt.evidence['original_execution_id'] == '101'
        assert attempt.evidence['resulting_execution_id'] == '102'
        assert attempt.evidence['verified_at'] and attempt.evidence['recovered_at']
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 7
    headers = {'Authorization': 'Bearer ' + context[3][0]}
    path = f'/api/v1/incidents/{data.incident_id}/recovery'
    response = context[0].get(path, headers=headers)
    assert response.json()['mode'] == 'real_n8n'
    assert response.json()['external_execution_id'] == '102'
    assert 'synthetic-private-key' not in response.text
    assert context[0].get(path, headers={'Authorization': 'Bearer ' + context[3][1]}).status_code == 404


@pytest.mark.parametrize('status', [400, 401, 403, 404, 429, 500, 503])
def test_action_http_failure_never_retries_post(context, status):
    data, config = setup(context)
    calls = []
    acts = activities(context, config, normal_handler(calls, action_status=status))
    prepare(acts, data)
    result = run(acts, data, 'retry')
    assert result.state == 'NEEDS_ATTENTION'
    assert run(acts, data, 'retry') == result
    assert [m for m, _ in calls].count('POST') == 1


@pytest.mark.parametrize('status,outcome', [('running', 'REAL_RECOVERY_UNVERIFIED'), ('error', 'REAL_RECOVERY_FAILED'),
                                        ('canceled', 'REAL_RECOVERY_FAILED'), ('crashed', 'REAL_RECOVERY_FAILED')])
def test_verification_must_observe_terminal_success(context, status, outcome):
    data, config = setup(context)
    acts = activities(context, config, normal_handler([], verify_status=status))
    prepare(acts, data)
    assert run(acts, data, 'retry').success
    assert run(acts, data, 'verify').state == 'NEEDS_ATTENTION'
    assert not run(acts, data, 'recover').success
    with context[1]() as db:
        assert db.get(Incident, UUID(data.incident_id)).verification_outcome == outcome


@pytest.mark.parametrize('change,reason', [
    ('credentials', 'N8N_MISSING_CREDENTIALS'), ('version', 'N8N_UNSUPPORTED_VERSION'),
    ('workflow', 'N8N_WORKFLOW_NOT_AUTHORIZED'), ('method', 'N8N_UNSUPPORTED_OPERATION'),
    ('idempotency', 'N8N_NON_IDEMPOTENT_OR_UNSAFE'), ('kind', 'N8N_NON_IDEMPOTENT_OR_UNSAFE'),
    ('mode', 'N8N_MODE_MISMATCH'), ('snapshot', 'N8N_WORKFLOW_SNAPSHOT_NOT_AUTHORIZED'),
    ('execution', 'N8N_INVALID_EXECUTION_ID'), ('financial', 'N8N_POLICY_DENIED')])
def test_authorization_failures(context, change, reason):
    data, config = setup(context)
    if change == 'credentials': config.n8n_api_key = type(config.n8n_api_key)('')
    if change == 'version': config.n8n_supported_version = '1.0'
    if change == 'workflow': config.n8n_authorizations = []
    if change == 'method': config.n8n_authorizations[0].operation = 'execute_command'
    if change == 'idempotency': config.n8n_authorizations[0].idempotent = False
    if change == 'mode': config.recovery_mode = 'mock-only'
    if change == 'snapshot': config.n8n_authorizations[0].workflow_sha256 = '0' * 64
    calls = []
    acts = activities(context, config, normal_handler(calls))
    prepare(acts, data)
    with context[1].begin() as db:
        incident = db.get(Incident, UUID(data.incident_id))
        if change == 'kind': db.get(Workflow, incident.workflow_id).kind = 'payment_v1'
        if change == 'financial': incident.failure_type = 'PAYMENT_RETRY'
        if change == 'execution': incident.source_execution_id = '../secret'
    result = run(acts, data, 'retry')
    assert result.state == 'NEEDS_ATTENTION' and result.reason == reason
    assert all(m != 'POST' for m, _ in calls)


@pytest.mark.parametrize('failure', ['malformed', 'network', 'identity', 'retry_identity', 'expired', 'retry_chain'])
def test_external_invalid_or_uncertain_results(context, failure):
    data, config = setup(context)
    calls = []
    normal = normal_handler(calls)
    def handler(req):
        if failure == 'expired' and req.method == 'GET': return httpx.Response(404)
        if failure == 'retry_chain' and req.method == 'GET':
            return httpx.Response(200, json={**execution('101', 'error', retry='99'), 'workflowData': SNAPSHOT})
        if req.method == 'POST':
            calls.append(('POST', req.url.path))
            if failure == 'network': raise httpx.ReadTimeout('secret payload', request=req)
            if failure == 'malformed': return httpx.Response(200, json={'id': 3})
            if failure == 'identity': return httpx.Response(200, json=execution(workflow='other-workflow'))
            if failure == 'retry_identity': return httpx.Response(200, json=execution(retry='999'))
        return normal(req)
    acts = activities(context, config, handler)
    prepare(acts, data)
    result = run(acts, data, 'retry')
    assert result.state == 'NEEDS_ATTENTION'
    assert 'secret' not in result.reason
    assert run(acts, data, 'retry') == result
    assert [m for m, _ in calls].count('POST') <= 1


def test_crash_after_reservation_does_not_resend(context):
    data, config = setup(context)
    calls = []
    def crash(req):
        calls.append(req.method)
        raise RuntimeError('simulated worker crash after reservation')
    acts = activities(context, config, crash)
    prepare(acts, data)
    with pytest.raises(ApplicationError): run(acts, data, 'retry')
    resumed = activities(context, config, normal_handler([]))
    result = run(resumed, data, 'retry')
    assert result.reason == 'N8N_ACTION_COMPLETION_UNKNOWN'
    assert calls == ['GET']


def test_scope_rejection_before_http(context):
    data, config = setup(context)
    acts = activities(context, config, lambda _: pytest.fail('HTTP forbidden'))
    with pytest.raises(ApplicationError) as exc:
        run(acts, replace(data, tenant_id=str(UUID(int=0))), 'retry')
    assert exc.value.non_retryable


def test_duplicate_external_action_across_failed_steps(context):
    data, config = setup(context)
    acts = activities(context, config, normal_handler([]))
    prepare(acts, data)
    assert run(acts, data, 'retry').success
    response = send(context, payload(event_id='another-step', source_execution_id='101', failed_step='other'))
    from app.temporal.schemas import RecoveryInput
    with context[1].begin() as db:
        inc = db.get(Incident, UUID(response.json()['incident_id']))
        inc.recovery_mode = 'real_n8n'
        second = RecoveryInput(str(inc.id), str(inc.tenant_id), str(inc.workflow_id), str(inc.integration_id), str(inc.id))
    prepare(acts, second)
    assert run(acts, second, 'retry').reason == 'N8N_DUPLICATE_EXTERNAL_ACTION'


def test_real_workflow_never_falls_back_to_mock(context, monkeypatch):
    data, config = setup(context)
    acts = activities(context, config, normal_handler([], action_status=503))
    async def execute(_, request, **kwargs):
        assert kwargs['retry_policy'].maximum_attempts == 3
        assert request.operation != 'fallback'
        return run(acts, data, request.operation)
    monkeypatch.setattr('app.temporal.workflows.workflow.execute_activity', execute)
    monkeypatch.setattr('app.temporal.workflows.workflow.patched', lambda _: True)
    assert asyncio.run(IncidentRecoveryWorkflow().run(data)).state == 'NEEDS_ATTENTION'


def test_mode_pinned_on_ingestion_and_duplicate_delivery(context):
    context[0].app.state.settings.recovery_mode = 'real_n8n'
    event = payload()
    first = send(context, event)
    context[0].app.state.settings.recovery_mode = 'mock-only'
    second = send(context, event)
    assert second.json()['duplicate'] and first.json()['incident_id'] == second.json()['incident_id']
    with context[1]() as db:
        assert db.get(Incident, UUID(first.json()['incident_id'])).recovery_mode == 'real_n8n'


@pytest.mark.parametrize('url', ['http://example.com', 'https://user:password@example.com', 'http://127.0.0.1/path'])
def test_base_url_rejects_insecure_or_embedded_secrets(url):
    with pytest.raises(N8nError):
        N8nClient(Settings(_env_file=None, n8n_base_url=url, n8n_api_key='private', n8n_supported_version='2.43.6'))


def test_mock_incident_stays_mock_when_real_mode_enabled(context):
    data = create_incident(context)
    config = Settings(_env_file=None, recovery_mode='real_n8n', ai_provider='mock')
    acts = activities(context, config, lambda _: pytest.fail('Mock incident must not contact n8n'))
    prepare(acts, data)
    for op in ['retry', 'verify', 'recover']:
        assert run(acts, data, op).success
    with context[1]() as db:
        assert db.get(Incident, UUID(data.incident_id)).verification_outcome == 'MOCK_VERIFIED'


def test_concurrent_activity_delivery_never_duplicates_external_post(context):
    from concurrent.futures import ThreadPoolExecutor
    data, config = setup(context)
    calls = []
    acts = activities(context, config, normal_handler(calls))
    prepare(acts, data)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: run(acts, data, 'retry'), range(3)))
    assert [m for m, _ in calls].count('POST') <= 1
    assert all(r.state in {'EXECUTING', 'NEEDS_ATTENTION'} for r in results)
    with context[1]() as db:
        assert db.scalar(select(func.count()).select_from(RecoveryAttempt)) == 1


def test_demo_provider_has_only_controlled_in_memory_effects():
    from fastapi.testclient import TestClient
    from scripts.n8n_demo_provider import app
    from uuid import uuid4
    with TestClient(app) as client:
        path = '/probe/' + str(uuid4())
        assert client.post(path).status_code == 503
        assert client.post(path).json()['side_effects'] == 'none'
        assert client.post(path).json()['status'] == 'success'


@pytest.mark.temporal_integration
@pytest.mark.skipif(__import__('os').environ.get('RUN_TEMPORAL_INTEGRATION') != '1', reason='Opt-in native Temporal server')
def test_native_temporal_real_adapter_lost_ack_and_replay(context):
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    from temporalio import activity
    from temporalio.worker import Worker, Replayer
    from app.temporal.client import start_recovery
    from app.temporal.schemas import StepResult, recovery_workflow_id
    from test_temporal_integration import server

    async def execute():
        data, config = setup(context)
        calls = []
        class LostAck(RecoveryActivities):
            @activity.defn(name='recovery_step')
            def step(self, request: StepRequest) -> StepResult:
                result = super().step(request)
                if request.operation == 'retry' and activity.info().attempt == 1:
                    raise ApplicationError('SYNTHETIC_LOST_ACK')
                return result
        acts = LostAck(context[1], config, n8n_client_factory=lambda s: N8nClient(s, httpx.MockTransport(normal_handler(calls))))
        async with await server() as environment:
            queue = 'cp6-test-' + uuid4().hex
            with ThreadPoolExecutor(max_workers=4) as executor:
                async with Worker(environment.client, task_queue=queue, workflows=[IncidentRecoveryWorkflow],
                                  activities=[acts.step], activity_executor=executor):
                    await start_recovery(environment.client, data, queue)
                    handle = environment.client.get_workflow_handle(recovery_workflow_id(data.tenant_id, data.incident_id))
                    result = await asyncio.wait_for(handle.result(), 90)
                    assert result['state'] == 'RECOVERED'
                    history = await handle.fetch_history()
                    budgets = {e.activity_task_scheduled_event_attributes.activity_id:
                        e.activity_task_scheduled_event_attributes.start_to_close_timeout.seconds
                        for e in history.events if e.HasField('activity_task_scheduled_event_attributes')}
                    assert list(budgets.values()).count(75) == 3  # Diagnosis, retry and verification.
                    await Replayer(workflows=[IncidentRecoveryWorkflow]).replay_workflow(history)
        assert [m for m, _ in calls].count('POST') == 1
    asyncio.run(execute())


def test_postgresql_migration_is_additive_without_live_database(monkeypatch):
    from io import StringIO
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://synthetic:synthetic@localhost/test')
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'), output_buffer=output)
    command.upgrade(config, '0003:0004', sql=True)
    sql = output.getvalue().upper()
    assert 'ADD COLUMN RECOVERY_MODE' in sql and 'CREATE UNIQUE INDEX' in sql
    assert all(word not in sql for word in ['DROP TABLE', 'TRUNCATE', 'DELETE FROM'])


def test_n8n_authorizations_env_parsing_requires_list(monkeypatch):
    import json
    from pydantic_core import ValidationError
    from app.core.config import Settings

    valid_auth = {
        'tenant_id': '0610d06e-460f-465e-8b19-f80b336fd8e7',
        'integration_id': '38979968-2d1f-4fd0-9307-c829e54ba58f',
        'workflow_external_id': 'ievg2u7YcfdnU3L8',
        'operation': 'retry_execution',
        'idempotent': True,
        'side_effect_safe': True,
        'workflow_sha256': '34562e136ce84efed16d4faa31d28e62d10613cb8c363c51e3a372791c12526b',
    }

    # Accidental dict serialization (e.g. from PowerShell pipeline unrolling) must fail
    monkeypatch.setenv('N8N_AUTHORIZATIONS', json.dumps(valid_auth))
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert 'Input should be a valid list' in str(exc.value)

    # Correct JSON list serialization must succeed
    monkeypatch.setenv('N8N_AUTHORIZATIONS', json.dumps([valid_auth]))
    settings = Settings()
    assert len(settings.n8n_authorizations) == 1
    assert str(settings.n8n_authorizations[0].tenant_id) == '0610d06e-460f-465e-8b19-f80b336fd8e7'


def test_temporal_pid_verification_pattern():
    import re
    # Windows command line pattern observed when running temporal.exe server start-dev
    sample_cmd = r'"C:\rebootx\backend\.temporal\cli\temporal.exe" server start-dev --ip 127.0.0.1 --db-filename C:\rebootx\backend\.temporal\rebootx-server.db'
    pattern = r'temporal.*server'
    assert re.search(pattern, sample_cmd) is not None
    assert re.search(pattern, 'other_process.exe server') is None


def test_n8n_webhook_readiness_error_messages():
    import re
    # When unregistered: n8n returns generic unregistered message
    unregistered_body = '{"code":404,"message":"The requested webhook \\"GET rebootx-safe-demo\\" is not registered."}'
    pattern = r'Did you mean to make a POST request'
    assert re.search(pattern, unregistered_body) is None

    # When registered for POST: n8n returns method suggestion message
    registered_body = '{"code":404,"message":"This webhook is not registered for GET requests. Did you mean to make a POST request?"}'
    assert re.search(pattern, registered_body) is not None



