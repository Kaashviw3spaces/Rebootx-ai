"""Real Temporal orchestration with mocked Gemma transport, never live inference."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner, Worker

from app.ai.diagnosis import DiagnosisEngine
from app.models.entities import Incident, IncidentDiagnosis, RecoveryAttempt
from app.temporal.activities import RecoveryActivities
from app.temporal.client import start_recovery
from app.temporal.schemas import RecoveryInput, StepRequest, StepResult, recovery_workflow_id
from app.temporal.workflows import IncidentRecoveryWorkflow
from test_ai import FakeProvider, output, settings
from test_recovery import create_incident
from test_temporal_integration import server

pytestmark = [pytest.mark.temporal_integration,
              pytest.mark.skipif(os.environ.get('RUN_TEMPORAL_INTEGRATION') != '1',
                                 reason='Opt-in native server; Gemma responses remain mocked.')]


class LostDiagnosisAcknowledgement(RecoveryActivities):
    @activity.defn(name='recovery_step')
    def step(self, request: StepRequest) -> StepResult:
        result = super().step(request)
        if request.operation == 'diagnose' and activity.info().attempt == 1:
            raise ApplicationError('SYNTHETIC_LOST_DIAGNOSIS_ACK')
        return result


def test_real_temporal_validated_ai_policy_persistence_and_retry(context):
    async def run():
        async with await server() as environment:
            config = settings()
            provider = FakeProvider()
            activities = LostDiagnosisAcknowledgement(context[1], config, DiagnosisEngine(config, provider))
            queue = 'ai-diagnosis-' + uuid4().hex
            with ThreadPoolExecutor(max_workers=4) as executor:
                async with Worker(environment.client, task_queue=queue, workflows=[IncidentRecoveryWorkflow],
                                  activities=[activities.step], activity_executor=executor):
                    cases = [
                        ('RATE_LIMIT', output(), 'RECOVERED', 'SUCCEEDED'),
                        ('NETWORK_FALLBACK_SUCCESS', output(recommended_action='USE_APPROVED_FALLBACK'), 'RECOVERED', 'SUCCEEDED'),
                        ('AUTHENTICATION_FAILURE', output(), 'NEEDS_ATTENTION', 'POLICY_REJECTED'),
                        ('NETWORK_RETRY_SUCCESS', output(confidence=0.1), 'NEEDS_ATTENTION', 'POLICY_REJECTED'),
                        ('NETWORK_FALLBACK_SUCCESS', output(alternative_actions=['ESCALATE']), 'NEEDS_ATTENTION', 'SUCCEEDED'),
                    ]
                    for index, (failure, response, state, status) in enumerate(cases):
                        provider.result = response
                        data = create_incident(context, failure, index)
                        await start_recovery(environment.client, data, queue)
                        handle = environment.client.get_workflow_handle(recovery_workflow_id(data.tenant_id, data.incident_id))
                        result = await asyncio.wait_for(handle.result(), 90)
                        assert result['state'] == state
                        history = await handle.fetch_history()
                        await Replayer(workflows=[IncidentRecoveryWorkflow]).replay_workflow(history)
                        budgets = [event.activity_task_scheduled_event_attributes.start_to_close_timeout.seconds
                                   for event in history.events if event.HasField('activity_task_scheduled_event_attributes')]
                        assert budgets.count(75) == 1 and all(value in {30, 75} for value in budgets)
                        with context[1]() as db:
                            assert db.get(Incident, UUID(data.incident_id)).status == state
                            diagnosis = db.scalar(select(IncidentDiagnosis).where(IncidentDiagnosis.incident_id == UUID(data.incident_id)))
                            assert diagnosis.status == status
                            assert db.scalar(select(func.count()).select_from(RecoveryAttempt).where(
                                RecoveryAttempt.incident_id == UUID(data.incident_id), RecoveryAttempt.action == 'MOCK_RETRY')) <= 1
                            if index == 4:
                                assert db.scalar(select(func.count()).select_from(RecoveryAttempt).where(
                                    RecoveryAttempt.incident_id == UUID(data.incident_id), RecoveryAttempt.action == 'MOCK_FALLBACK')) == 0
                    assert len(provider.calls) == len(cases)  # Redelivery after commit never repeats inference.
    asyncio.run(run())


@workflow.defn(name='IncidentRecoveryWorkflow')
class LegacyTimeoutWorkflow:
    """Test-only pre-patch authentication-escalation history with original budgets."""
    @workflow.run
    async def run(self, data: RecoveryInput) -> StepResult:
        async def step(operation, reason=''):
            return await workflow.execute_activity(
                'recovery_step', StepRequest(data, operation, reason), result_type=StepResult,
                start_to_close_timeout=timedelta(seconds=30), schedule_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1), maximum_interval=timedelta(seconds=5), maximum_attempts=3))
        await step('accept')
        diagnosis = await step('diagnose')
        return await step('escalate', diagnosis.category)


def test_pre_patch_history_replays_with_current_diagnosis_timeouts(context):
    async def run():
        async with await server() as environment:
            queue = 'legacy-timeouts-' + uuid4().hex
            data = create_incident(context, 'AUTHENTICATION_FAILURE')
            with ThreadPoolExecutor(max_workers=4) as executor:
                # The test-only workflow module imports pytest/DB helpers. Production remains sandboxed.
                async with Worker(environment.client, task_queue=queue, workflows=[LegacyTimeoutWorkflow],
                                  workflow_runner=UnsandboxedWorkflowRunner(),
                                  activities=[RecoveryActivities(context[1]).step], activity_executor=executor):
                    await start_recovery(environment.client, data, queue)
                    handle = environment.client.get_workflow_handle(recovery_workflow_id(data.tenant_id, data.incident_id))
                    assert (await asyncio.wait_for(handle.result(), 90))['state'] == 'NEEDS_ATTENTION'
                    history = await handle.fetch_history()
            assert all(event.activity_task_scheduled_event_attributes.start_to_close_timeout.seconds == 30
                       for event in history.events if event.HasField('activity_task_scheduled_event_attributes'))
            await Replayer(workflows=[IncidentRecoveryWorkflow]).replay_workflow(history)
    asyncio.run(run())


def test_native_fast_path_and_ambiguous_routing_preserve_source_and_redelivery(context):
    from test_fast_path import new_failure
    async def run():
        async with await server() as environment:
            config = settings(ai_fast_path_enabled=True)
            provider = FakeProvider()
            activities = LostDiagnosisAcknowledgement(context[1], config, DiagnosisEngine(config, provider))
            queue = 'fast-routing-' + uuid4().hex
            with ThreadPoolExecutor(max_workers=4) as executor:
                async with Worker(environment.client, task_queue=queue, workflows=[IncidentRecoveryWorkflow],
                                  activities=[activities.step], activity_executor=executor):
                    cases = [('UNKNOWN_FAILURE', 429, 'deterministic', 'RECOVERED'),
                             ('UNKNOWN_FAILURE', 401, 'deterministic', 'NEEDS_ATTENTION'),
                             ('UNKNOWN_FAILURE', 503, 'deterministic', 'RECOVERED'),
                             ('CONNECTION_TIMEOUT', None, 'deterministic', 'RECOVERED'),
                             ('SCHEMA_VALIDATION_ERROR', None, 'deterministic', 'NEEDS_ATTENTION'),
                             ('UNKNOWN_FAILURE', 500, 'gemma', 'RECOVERED')]
                    for index, (code, status, source, expected) in enumerate(cases):
                        data = new_failure(context, code, status, index)
                        await start_recovery(environment.client, data, queue)
                        handle = environment.client.get_workflow_handle(recovery_workflow_id(data.tenant_id, data.incident_id))
                        assert (await asyncio.wait_for(handle.result(), 90))['state'] == expected
                        await Replayer(workflows=[IncidentRecoveryWorkflow]).replay_workflow(await handle.fetch_history())
                        with context[1]() as db:
                            record = db.scalar(select(IncidentDiagnosis).where(IncidentDiagnosis.incident_id == UUID(data.incident_id)))
                            assert record.provider == record.source == source
                            assert db.scalar(select(func.count()).select_from(IncidentDiagnosis).where(
                                IncidentDiagnosis.incident_id == UUID(data.incident_id))) == 1
                    assert len(provider.calls) == 1  # Ambiguous only; committed redelivery never infers again.
    asyncio.run(run())
