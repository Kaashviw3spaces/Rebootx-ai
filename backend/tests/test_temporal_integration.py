"""Opt-in real native server tests, separate from mocked workflow unit tests."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from app.models.entities import Incident, RecoveryAttempt, RecoveryOutbox
from app.temporal.activities import RecoveryActivities
from app.temporal.client import start_recovery
from app.temporal.dispatcher import OutboxDispatcher
from app.temporal.schemas import StepRequest, StepResult, recovery_workflow_id
from app.temporal.workflows import IncidentRecoveryWorkflow
from app.core.config import Settings
from test_recovery import create_incident

pytestmark = [pytest.mark.temporal_integration,
              pytest.mark.skipif(os.environ.get('RUN_TEMPORAL_INTEGRATION') != '1',
                                 reason='Set RUN_TEMPORAL_INTEGRATION=1 for a real Temporal server.')]


async def server():
    binary = os.environ.get('TEMPORAL_CLI_PATH')
    cached = Path('.temporal/cli/temporal.exe').resolve()
    if not binary and cached.exists():
        binary = str(cached)
    return await WorkflowEnvironment.start_local(dev_server_existing_path=binary,
                                                  download_dest_dir=str(Path('.temporal').resolve()))


class LostAcknowledgementActivities(RecoveryActivities):
    def __init__(self, sessions):
        super().__init__(sessions)
        self.delivery_attempts = []

    @activity.defn(name='recovery_step')
    def step(self, request: StepRequest) -> StepResult:
        result = super().step(request)
        if request.operation == 'retry':
            self.delivery_attempts.append(activity.info().attempt)
            if activity.info().attempt == 1:
                raise ApplicationError('SYNTHETIC_LOST_ACTIVITY_ACK')
        return result


def test_real_server_lifecycle_retries_duplicate_start_and_replay(context):
    async def run():
        async with await server() as env:
            queue = 'integration-' + uuid4().hex
            activities = LostAcknowledgementActivities(context[1])
            with ThreadPoolExecutor(max_workers=8) as executor:
                async with Worker(env.client, task_queue=queue, workflows=[IncidentRecoveryWorkflow],
                                  activities=[activities.step], activity_executor=executor):
                    cases = [('NETWORK_RETRY_SUCCESS', 'RECOVERED'), ('RATE_LIMIT', 'RECOVERED'),
                             ('NETWORK_FALLBACK_SUCCESS', 'RECOVERED'), ('NETWORK_BOTH_FAIL', 'NEEDS_ATTENTION'),
                             ('NETWORK_VERIFY_FAIL', 'NEEDS_ATTENTION'), ('AUTHENTICATION_FAILURE', 'NEEDS_ATTENTION'),
                             ('INVALID_PAYLOAD', 'NEEDS_ATTENTION'), ('UNKNOWN_FAILURE', 'NEEDS_ATTENTION')]
                    dispatcher = OutboxDispatcher(context[1], Settings(temporal_task_queue=queue), env.client)
                    for index, (category, state) in enumerate(cases):
                        data = create_incident(context, category, index)
                        assert await dispatcher.dispatch_one()
                        # A second actual server start request must reuse the first execution.
                        await start_recovery(env.client, data, queue)
                        handle = env.client.get_workflow_handle(recovery_workflow_id(data.tenant_id, data.incident_id))
                        result = await asyncio.wait_for(handle.result(), 90)
                        assert result['state'] == state
                        await Replayer(workflows=[IncidentRecoveryWorkflow]).replay_workflow(await handle.fetch_history())
                        with context[1]() as db:
                            assert db.get(Incident, UUID(data.incident_id)).status == state
                            assert db.scalar(select(RecoveryOutbox).where(RecoveryOutbox.incident_id == UUID(data.incident_id))).dispatched_at
                            assert db.scalar(select(func.count()).select_from(RecoveryAttempt).where(
                                RecoveryAttempt.incident_id == UUID(data.incident_id), RecoveryAttempt.action == 'MOCK_RETRY')) <= 1
                    assert 1 in activities.delivery_attempts and 2 in activities.delivery_attempts
    asyncio.run(run())


@pytest.mark.worker_restart
def test_actual_worker_process_crash_after_commit_then_restart(context):
    async def run():
        async with await server() as env:
            data = create_incident(context)
            queue = 'restart-' + uuid4().hex
            child_env = os.environ.copy()
            child_env.update(TEMPORAL_ADDRESS=env.client.service_client.config.target_host,
                             TEMPORAL_NAMESPACE='default', TEMPORAL_TASK_QUEUE=queue,
                             TEMPORAL_TLS_ENABLED='false', TEMPORAL_API_KEY='')
            engine = context[4]
            url = engine.url
            if engine.dialect.name == 'postgresql':
                with engine.connect() as connection:
                    schema = connection.exec_driver_sql('SELECT current_schema()').scalar()
                assert schema.startswith('test_') and len(schema) == 37
                url = url.update_query_dict({'options': '-csearch_path=' + schema})
            child_env['DATABASE_URL'] = url.render_as_string(hide_password=False)
            child_env['REBOOTX_TEST_CRASH_AFTER_RETRY'] = '1'
            processes = []
            try:
                process = subprocess.Popen([sys.executable, 'tests/restart_worker.py'], env=child_env,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(process)
                await start_recovery(env.client, data, queue)
                # The test worker exits abruptly only after committing the mock retry,
                # before returning its activity acknowledgement to Temporal.
                for _ in range(120):
                    if process.poll() is not None:
                        break
                    await asyncio.sleep(0.5)
                assert process.poll() == 23, 'Test worker did not reach the deliberate crash point.'
                with context[1]() as db:
                    assert db.get(Incident, UUID(data.incident_id)).status == 'EXECUTING'
                    assert db.scalar(select(func.count()).select_from(RecoveryAttempt)) == 1
                child_env['REBOOTX_TEST_CRASH_AFTER_RETRY'] = '0'
                replacement = subprocess.Popen([sys.executable, 'tests/restart_worker.py'], env=child_env,
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(replacement)
                handle = env.client.get_workflow_handle(recovery_workflow_id(data.tenant_id, data.incident_id))
                result = await asyncio.wait_for(handle.result(), 100)
                assert result['state'] == 'RECOVERED'
                with context[1]() as db:
                    assert db.scalar(select(func.count()).select_from(RecoveryAttempt)) == 1
                    assert db.get(Incident, UUID(data.incident_id)).verification_outcome == 'MOCK_VERIFIED'
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                    await asyncio.to_thread(process.wait, timeout=15)
    asyncio.run(run())
