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
        real_mode = False
        async def step(operation, reason=''):
            start_seconds, schedule_seconds = 30, 120
            if operation == 'diagnose' and workflow.patched('diagnosis-timeouts-v1'):
                # AI configuration is bounded at <=60s; history records the versioned budget.
                # 3*75s plus retry/queue headroom fits the unchanged 20-minute workflow deadline.
                start_seconds, schedule_seconds = 75, 240
            if real_mode and operation in {'retry', 'verify'} and workflow.patched('real-n8n-budgets-v1'):
                start_seconds, schedule_seconds = 75, 240
            return await workflow.execute_activity(
                'recovery_step', StepRequest(data, operation, reason), result_type=StepResult,
                start_to_close_timeout=timedelta(seconds=start_seconds),
                schedule_to_close_timeout=timedelta(seconds=schedule_seconds),
                retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1),
                                         maximum_interval=timedelta(seconds=5), maximum_attempts=3),
            )

        try:
            await step('accept')
            diagnosis = await step('diagnose')
            real_mode = diagnosis.mode == 'real_n8n'
            if diagnosis.category not in {'TRANSIENT_NETWORK_FAILURE', 'RATE_LIMIT'}:
                return await step('escalate', diagnosis.category)
            await step('plan')
            if diagnosis.delay_seconds:
                await workflow.sleep(timedelta(seconds=diagnosis.delay_seconds))
            outcome = await step('retry')
            if workflow.patched('real-n8n-terminal-v1') and outcome.state == 'NEEDS_ATTENTION':
                return outcome
            if not outcome.success:
                outcome = await step('fallback')
            if not outcome.success:
                return await step('escalate', 'MOCK_ACTIONS_EXHAUSTED')
            verified = await step('verify')
            if workflow.patched('real-n8n-terminal-v1') and verified.state == 'NEEDS_ATTENTION':
                return verified
            if not verified.success:
                return await step('escalate', 'MOCK_VERIFICATION_FAILED')
            return await step('recover')
        except ActivityError:
            # The escalation activity is bounded too. A database outage or
            # scope denial can still fail it; never fabricate persisted success.
            return await step('escalate', 'ACTIVITY_FAILURE')
