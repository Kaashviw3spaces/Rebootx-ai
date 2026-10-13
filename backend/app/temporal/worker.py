import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import logging

from temporalio.worker import Worker

from app.core.config import Settings
from app.core.database import make_engine, session_factory
from app.temporal.activities import RecoveryActivities
from app.temporal.client import connect_temporal
from app.temporal.logging import log_event
from app.temporal.workflows import IncidentRecoveryWorkflow


async def run_worker():
    settings = Settings()
    client = await connect_temporal(settings)
    engine = make_engine(settings.database_url.get_secret_value())
    try:
        activities = RecoveryActivities(session_factory(engine))
        with ThreadPoolExecutor(max_workers=8) as executor:
            worker = Worker(client, task_queue=settings.temporal_task_queue,
                            workflows=[IncidentRecoveryWorkflow], activities=[activities.step],
                            activity_executor=executor, max_concurrent_activities=8,
                            graceful_shutdown_timeout=timedelta(seconds=10))
            log_event('mock_recovery_worker_started')
            await worker.run()
    finally:
        engine.dispose()


def main():
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass
    except Exception:
        log_event('worker_stopped', error_code='WORKER_STARTUP_FAILURE')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
