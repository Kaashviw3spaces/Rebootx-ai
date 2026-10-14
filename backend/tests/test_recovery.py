import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy import text
from alembic import command
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError
from temporalio.testing import ActivityEnvironment

from app.core.config import Settings
from app.models.entities import AuditLog, Incident, RecoveryAttempt, RecoveryOutbox, utcnow
from app.temporal.activities import RecoveryActivities
from app.temporal.client import connect_temporal, start_recovery
from app.temporal.dispatcher import OutboxDispatcher
from app.temporal.schemas import RecoveryInput, StepRequest, recovery_workflow_id
from app.temporal.workflows import IncidentRecoveryWorkflow
from test_backend import payload, send


def create_incident(context, category='NETWORK_RETRY_SUCCESS', index=0):
    result = send(context, payload(event_id=f'recovery-{index}', source_execution_id=f'recovery-exec-{index}',
                                   error={'category': category, 'message': 'synthetic private message'}))
    assert result.status_code == 202
    with context[1]() as db:
        item = db.get(Incident, UUID(result.json()['incident_id']))
        return RecoveryInput(str(item.id), str(item.tenant_id), str(item.workflow_id), str(item.integration_id), str(item.id))


def test_mock_lifecycle_matrix_with_sdk_activity_environment(context, monkeypatch):
    activities = RecoveryActivities(context[1])
    environment = ActivityEnvironment()
    sleeps = []

    async def execute(_, request, **kwargs):
        assert kwargs['retry_policy'].maximum_attempts == 3
        return environment.run(activities.step, request)

    async def sleep(delay):
        sleeps.append(delay.total_seconds())

    monkeypatch.setattr('app.temporal.workflows.workflow.execute_activity', execute)
    monkeypatch.setattr('app.temporal.workflows.workflow.sleep', sleep)
    monkeypatch.setattr('app.temporal.workflows.workflow.patched', lambda _: True)
    cases = [
        ('NETWORK_RETRY_SUCCESS', 'RECOVERED', ['MOCK_RETRY'], None),
        ('NETWORK_FALLBACK_SUCCESS', 'RECOVERED', ['MOCK_RETRY', 'MOCK_FALLBACK'], None),
        ('NETWORK_BOTH_FAIL', 'NEEDS_ATTENTION', ['MOCK_RETRY', 'MOCK_FALLBACK', 'ESCALATE'], 'MOCK_ACTIONS_EXHAUSTED'),
        ('NETWORK_VERIFY_FAIL', 'NEEDS_ATTENTION', ['MOCK_RETRY', 'ESCALATE'], 'MOCK_VERIFICATION_FAILED'),
        ('RATE_LIMIT', 'RECOVERED', ['MOCK_RETRY'], None),
        ('AUTHENTICATION_FAILURE', 'NEEDS_ATTENTION', ['ESCALATE'], 'AUTHENTICATION_FAILURE'),
        ('INVALID_PAYLOAD', 'NEEDS_ATTENTION', ['ESCALATE'], 'INVALID_PAYLOAD'),
        ('UNRECOGNIZED_FIXTURE', 'NEEDS_ATTENTION', ['ESCALATE'], 'UNKNOWN_FAILURE'),
    ]
    for index, (category, state, actions, reason) in enumerate(cases):
        data = create_incident(context, category, index)
        result = asyncio.run(IncidentRecoveryWorkflow().run(data))
        assert result.state == state
        with context[1]() as db:
            item = db.get(Incident, UUID(data.incident_id))
            attempts = db.scalars(select(RecoveryAttempt).where(RecoveryAttempt.incident_id == item.id)
                                  .order_by(RecoveryAttempt.started_at)).all()
            assert item.status == state and item.recovery_reason == reason
            assert [a.action for a in attempts] == actions
            assert all(a.started_at and a.ended_at for a in attempts)
            assert all(a.adapter == 'mock-only-v1' for a in attempts)
            assert item.verification_outcome == ('MOCK_VERIFIED' if state == 'RECOVERED' else
                                                  'MOCK_FAILED' if category == 'NETWORK_VERIFY_FAIL' else None)
    assert sleeps == [2]


def test_activity_and_audit_idempotency_and_no_state_regression(context):
    data = create_incident(context)
    env, activities = ActivityEnvironment(), RecoveryActivities(context[1])
    results = {}
    for operation in ['accept', 'diagnose', 'plan', 'retry', 'verify', 'recover']:
        request = StepRequest(data, operation)
        first = env.run(activities.step, request)
        assert env.run(activities.step, request) == first
        results[operation] = first
    assert env.run(activities.step, StepRequest(data, 'accept')) == results['accept']
    with context[1]() as db:
        assert db.get(Incident, UUID(data.incident_id)).status == 'RECOVERED'
        assert db.scalar(select(func.count()).select_from(RecoveryAttempt)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 7


def test_concurrent_activity_redelivery_creates_one_attempt(context):
    data = create_incident(context)
    activities = RecoveryActivities(context[1])
    for op in ['accept', 'diagnose', 'plan']:
        ActivityEnvironment().run(activities.step, StepRequest(data, op))
    def run(_):
        return ActivityEnvironment().run(activities.step, StepRequest(data, 'retry'))
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert all(r.success for r in pool.map(run, range(3)))
    with context[1]() as db:
        assert db.scalar(select(func.count()).select_from(RecoveryAttempt)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.event_type == 'RECOVERY_RETRY')) == 1


def test_activity_scope_and_unsafe_actions_fail_closed(context):
    data = create_incident(context, 'AUTHENTICATION_FAILURE')
    env, activities = ActivityEnvironment(), RecoveryActivities(context[1])
    for bad in [replace(data, tenant_id=str(uuid4())), replace(data, workflow_id=str(uuid4())),
                replace(data, integration_id=str(uuid4())), replace(data, version=2)]:
        with pytest.raises(ApplicationError) as exc:
            env.run(activities.step, StepRequest(bad, 'accept'))
        assert exc.value.non_retryable
    for op in ['accept', 'diagnose']:
        env.run(activities.step, StepRequest(data, op))
    for op in ['plan', 'retry', 'recover', 'shell']:
        with pytest.raises(ApplicationError):
            env.run(activities.step, StepRequest(data, op))
    with context[1]() as db:
        assert db.scalar(select(func.count()).select_from(RecoveryAttempt)) == 0


def test_read_endpoints_are_tenant_authorized_and_redacted(context):
    data = create_incident(context)
    env, activities = ActivityEnvironment(), RecoveryActivities(context[1])
    for op in ['accept', 'diagnose', 'plan', 'retry', 'verify', 'recover']:
        env.run(activities.step, StepRequest(data, op))
    client, _, _, tokens, _, _ = context
    for suffix in ['recovery', 'attempts', 'timeline']:
        path = f'/api/v1/incidents/{data.incident_id}/{suffix}'
        assert client.get(path).status_code == 401
        assert client.get(path, headers={'Authorization': 'Bearer ' + tokens[1]}).status_code == 404
        response = client.get(path, headers={'Authorization': 'Bearer ' + tokens[0]})
        assert response.status_code == 200
        assert 'synthetic private message' not in response.text
        assert tokens[0] not in response.text
    response = client.get(f'/api/v1/incidents/{data.incident_id}/recovery',
                          headers={'Authorization': 'Bearer ' + tokens[0]}).json()
    assert response['mode'] == 'mock-only' and response['verification_outcome'] == 'MOCK_VERIFIED'


def test_webhook_and_outbox_commit_atomically_and_deduplicate(context):
    data = create_incident(context)
    repeat = send(context, payload(event_id='recovery-0', source_execution_id='recovery-exec-0'))
    assert repeat.json()['incident_id'] == data.incident_id and repeat.json()['duplicate']
    with context[1]() as db:
        assert db.scalar(select(func.count()).select_from(RecoveryOutbox)) == 1
    sessions = context[0].app.state.sessions
    def fail_outbox(db, *_):
        if any(isinstance(obj, RecoveryOutbox) for obj in db.new):
            raise RuntimeError('synthetic outbox write failure')
    event.listen(sessions, 'before_flush', fail_outbox)
    try:
        with pytest.raises(RuntimeError):
            send(context, payload(event_id='outbox-failed', source_execution_id='outbox-failed'))
    finally:
        event.remove(sessions, 'before_flush', fail_outbox)
    with context[1]() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 1
        assert db.scalar(select(func.count()).select_from(RecoveryOutbox)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_dispatch_retry_duplicate_start_and_lost_ack(context, monkeypatch):
    data = create_incident(context)
    client = AsyncMock()
    client.start_workflow.side_effect = RuntimeError('secret diagnostic must not be persisted')
    dispatcher = OutboxDispatcher(context[1], Settings(), client)
    assert asyncio.run(dispatcher.dispatch_one())
    with context[1].begin() as db:
        outbox = db.scalar(select(RecoveryOutbox))
        assert outbox.last_error == 'TEMPORAL_DISPATCH_FAILED' and outbox.attempt_count == 1
        assert outbox.dispatched_at is None
        outbox.next_attempt_at = utcnow() - timedelta(seconds=1)
    client.start_workflow.side_effect = WorkflowAlreadyStartedError(recovery_workflow_id(data.tenant_id, data.incident_id), 'IncidentRecoveryWorkflow')
    assert asyncio.run(dispatcher.dispatch_one())
    with context[1]() as db:
        assert db.scalar(select(RecoveryOutbox)).dispatched_at is not None
    assert not asyncio.run(dispatcher.dispatch_one())
    kwargs = client.start_workflow.call_args.kwargs
    assert kwargs['id'] == recovery_workflow_id(data.tenant_id, data.incident_id)
    assert kwargs['id_reuse_policy'].name == 'REJECT_DUPLICATE'
    assert kwargs['id_conflict_policy'].name == 'FAIL'
    # Simulate start success followed by a failed DB acknowledgement.
    other = create_incident(context, index=1)
    client.start_workflow.side_effect = None
    original_finish = dispatcher.finish
    monkeypatch.setattr(dispatcher, 'finish', lambda *_: (_ for _ in ()).throw(RuntimeError('synthetic DB failure')))
    with pytest.raises(RuntimeError):
        asyncio.run(dispatcher.dispatch_one())
    monkeypatch.setattr(dispatcher, 'finish', original_finish)
    with context[1].begin() as db:
        db.execute(update(RecoveryOutbox).where(RecoveryOutbox.incident_id == UUID(other.incident_id))
                   .values(lease_expires_at=utcnow() - timedelta(seconds=1)))
    client.start_workflow.side_effect = WorkflowAlreadyStartedError('same', 'IncidentRecoveryWorkflow')
    assert asyncio.run(dispatcher.dispatch_one())


def test_dispatch_lease_fencing_and_restart(context):
    create_incident(context)
    first = OutboxDispatcher(context[1], Settings(), AsyncMock())
    claim = first.claim()
    second = OutboxDispatcher(context[1], Settings(), AsyncMock())
    assert second.claim() is None
    with context[1].begin() as db:
        db.execute(update(RecoveryOutbox).values(lease_expires_at=utcnow() - timedelta(seconds=1)))
    reclaimed = second.claim()
    assert reclaimed and reclaimed.token != claim.token
    assert not first.finish(claim)
    assert second.finish(reclaimed)


@pytest.mark.parametrize('start_fails', [False, True])
def test_dispatch_reclaimed_lease_does_not_log_acknowledgement(context, caplog, start_fails):
    create_incident(context)
    client = AsyncMock()
    dispatcher = OutboxDispatcher(context[1], Settings(), client)
    replacement = OutboxDispatcher(context[1], Settings(), AsyncMock())
    reclaimed = []

    async def reclaim_during_start(*args, **kwargs):
        with context[1].begin() as db:
            db.execute(update(RecoveryOutbox).values(lease_expires_at=utcnow() - timedelta(seconds=1)))
        reclaimed.append(replacement.claim())
        assert reclaimed[0] is not None
        if start_fails:
            raise ConnectionError('synthetic start failure')

    client.start_workflow.side_effect = reclaim_during_start
    with caplog.at_level(logging.INFO, logger='rebootx.recovery'):
        assert asyncio.run(dispatcher.dispatch_one())
    events = [json.loads(record.message)['event'] for record in caplog.records
              if record.name == 'rebootx.recovery']
    assert 'recovery_dispatched' not in events
    assert 'dispatch_retry_scheduled' not in events
    assert 'dispatch_acknowledgement_rejected' in events
    with context[1]() as db:
        outbox = db.scalar(select(RecoveryOutbox))
        assert outbox.lease_token == reclaimed[0].token
        assert outbox.dispatched_at is None and outbox.last_error is None
    assert replacement.finish(reclaimed[0])


def test_temporal_connection_failure_records_retry(context, monkeypatch):
    create_incident(context)
    monkeypatch.setattr('app.temporal.dispatcher.connect_temporal', AsyncMock(side_effect=ConnectionError('synthetic secret')))
    dispatcher = OutboxDispatcher(context[1], Settings())
    assert asyncio.run(dispatcher.dispatch_one())
    with context[1]() as db:
        outbox = db.scalar(select(RecoveryOutbox))
        assert outbox.last_error == 'TEMPORAL_DISPATCH_FAILED' and outbox.dispatched_at is None


def test_remote_temporal_requires_tls_and_api_key_is_secret():
    for settings in [Settings(temporal_address='remote.example:7233'), Settings(temporal_api_key='synthetic-key')]:
        with pytest.raises(ValueError, match='TEMPORAL_TLS_REQUIRED'):
            asyncio.run(connect_temporal(settings))
        assert 'synthetic-key' not in repr(settings)


def test_activity_database_failure_suppresses_original_exception(context):
    data = create_incident(context)
    class FailingSessions:
        def begin(self):
            raise RuntimeError('synthetic-password-and-database-url')
    with pytest.raises(ApplicationError) as exc:
        ActivityEnvironment().run(RecoveryActivities(FailingSessions()).step, StepRequest(data, 'accept'))
    assert str(exc.value) == 'RecoveryDatabaseFailure: RECOVERY_DATABASE_FAILURE'
    assert exc.value.__suppress_context__


def test_incremental_migration_preserves_historical_records(context):
    data = create_incident(context)
    for op in ['accept', 'diagnose', 'plan', 'retry']:
        ActivityEnvironment().run(RecoveryActivities(context[1]).step, StepRequest(data, op))
    # Only this fixture's disposable schema/database is downgraded to model
    # an existing Checkpoint 1 deployment. Public Neon data is never touched.
    engine, config = context[4], context[5]
    tables = ['tenants', 'integrations', 'workflows', 'incidents', 'recovery_attempts', 'audit_logs']
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.downgrade(config, '0001')
        counts = {t: connection.scalar(text(f'SELECT count(*) FROM {t}')) for t in tables}
        command.upgrade(config, 'head')
        assert counts == {t: connection.scalar(text(f'SELECT count(*) FROM {t}')) for t in tables}
        assert connection.scalar(text('SELECT count(*) FROM recovery_outbox')) == 0
        assert connection.scalar(text('SELECT count(*) FROM recovery_attempts WHERE logical_key IS NULL')) == 1
        command.check(config)
