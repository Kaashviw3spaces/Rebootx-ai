"""Deterministic orchestration: activities do every database/external operation."""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from app.temporal.schemas import RecoveryInput, StepRequest, StepResult


@workflow.defn(name='IncidentRecoveryWorkflow')
class IncidentRecoveryWorkflow:
    @workflow.run
    async def run(self, data: RecoveryInput) -> StepResult:
        async def step(operation, reason=''):
            return await workflow.execute_activity(
                'recovery_step', StepRequest(data, operation, reason), result_type=StepResult,
                start_to_close_timeout=timedelta(seconds=30),
                schedule_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1),
                                         maximum_interval=timedelta(seconds=5), maximum_attempts=3),
            )

        try:
            await step('accept')
            diagnosis = await step('diagnose')
            if diagnosis.category not in {'TRANSIENT_NETWORK_FAILURE', 'RATE_LIMIT'}:
                return await step('escalate', diagnosis.category)
            await step('plan')
            if diagnosis.delay_seconds:
                await workflow.sleep(timedelta(seconds=diagnosis.delay_seconds))
            outcome = await step('retry')
            if not outcome.success:
                outcome = await step('fallback')
            if not outcome.success:
                return await step('escalate', 'MOCK_ACTIONS_EXHAUSTED')
            verified = await step('verify')
            if not verified.success:
                return await step('escalate', 'MOCK_VERIFICATION_FAILED')
            return await step('recover')
        except ActivityError:
            # The escalation activity is bounded too. A database outage or
            # scope denial can still fail it; never fabricate persisted success.
            return await step('escalate', 'ACTIVITY_FAILURE')
