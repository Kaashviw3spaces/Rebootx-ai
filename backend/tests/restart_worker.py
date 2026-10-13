"""Test-only worker that abruptly exits after a committed mock action (no external effects)."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from temporalio import activity
from temporalio.worker import Worker

from app.core.config import Settings
from app.core.database import make_engine, session_factory
from app.temporal.activities import RecoveryActivities
from app.temporal.client import connect_temporal
from app.temporal.schemas import StepRequest, StepResult
from app.temporal.workflows import IncidentRecoveryWorkflow


class CrashActivities(RecoveryActivities):
    @activity.defn(name='recovery_step')
    def step(self, request: StepRequest) -> StepResult:
        result = super().step(request)
        if request.operation == 'retry' and os.environ.get('REBOOTX_TEST_CRASH_AFTER_RETRY') == '1':
            os._exit(23)
        return result


async def main():
    settings = Settings()
    engine = make_engine(settings.database_url.get_secret_value())
    client = await connect_temporal(settings)
    activities = CrashActivities(session_factory(engine))
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            await Worker(client, task_queue=settings.temporal_task_queue, workflows=[IncidentRecoveryWorkflow],
                         activities=[activities.step], activity_executor=executor).run()
    finally:
        engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
