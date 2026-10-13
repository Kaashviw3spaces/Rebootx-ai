import asyncio
from datetime import timedelta

from temporalio.client import Client
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.core.config import Settings
from app.temporal.schemas import RecoveryInput, recovery_workflow_id
from app.temporal.workflows import IncidentRecoveryWorkflow


async def connect_temporal(settings: Settings) -> Client:
    key = settings.temporal_api_key.get_secret_value()
    host = settings.temporal_address.rsplit(':', 1)[0]
    local = host in {'127.0.0.1', 'localhost', '[::1]'}
    if (key or not local) and not settings.temporal_tls_enabled:
        raise ValueError('TEMPORAL_TLS_REQUIRED')
    return await asyncio.wait_for(Client.connect(
        settings.temporal_address, namespace=settings.temporal_namespace,
        tls=settings.temporal_tls_enabled, api_key=key or None,
        identity='rebootx-checkpoint-2',
    ), timeout=10)


async def start_recovery(client: Client, data: RecoveryInput, task_queue: str):
    identifier = recovery_workflow_id(data.tenant_id, data.incident_id)
    try:
        await client.start_workflow(
            IncidentRecoveryWorkflow.run, data, id=identifier, task_queue=task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
            execution_timeout=timedelta(minutes=20), run_timeout=timedelta(minutes=20),
            task_timeout=timedelta(seconds=10), retry_policy=RetryPolicy(maximum_attempts=1),
            rpc_timeout=timedelta(seconds=10),
        )
    except WorkflowAlreadyStartedError:
        # Includes completed executions retained in server history. Never
        # start a second recovery after a lost start acknowledgement.
        pass
