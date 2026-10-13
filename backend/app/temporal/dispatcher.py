"""Durable outbox dispatcher; independent of FastAPI and of the activity worker."""
import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update

from app.core.config import Settings
from app.core.database import make_engine, session_factory
from app.models.entities import Incident, RecoveryOutbox, utcnow
from app.temporal.client import connect_temporal, start_recovery
from app.temporal.logging import log_event
from app.temporal.schemas import RecoveryInput, recovery_workflow_id


@dataclass(frozen=True)
class Claim:
    outbox_id: UUID
    token: UUID
    data: RecoveryInput
    attempt_count: int


class OutboxDispatcher:
    def __init__(self, sessions, settings: Settings, client=None):
        self.sessions, self.settings, self.client = sessions, settings, client

    def claim(self) -> Claim | None:
        now, token = utcnow(), uuid4()
        due = (RecoveryOutbox.dispatched_at.is_(None), RecoveryOutbox.next_attempt_at <= now,
               or_(RecoveryOutbox.lease_expires_at.is_(None), RecoveryOutbox.lease_expires_at <= now))
        with self.sessions.begin() as db:
            event = db.scalar(select(RecoveryOutbox).where(*due)
                              .order_by(RecoveryOutbox.next_attempt_at, RecoveryOutbox.id)
                              .with_for_update(skip_locked=True).limit(1))
            if event is None:
                return None
            # Conditional update also makes claiming safe on SQLite, which
            # does not implement SELECT FOR UPDATE.
            changed = db.execute(update(RecoveryOutbox).where(
                RecoveryOutbox.id == event.id, RecoveryOutbox.tenant_id == event.tenant_id, *due,
            ).values(lease_token=token, lease_expires_at=now + timedelta(seconds=60),
                     attempt_count=RecoveryOutbox.attempt_count + 1),
                execution_options={'synchronize_session': False}).rowcount
            if changed != 1:
                return None
            incident = db.scalar(select(Incident).where(
                Incident.id == event.incident_id, Incident.tenant_id == event.tenant_id))
            if incident is None:
                raise ValueError('OUTBOX_SCOPE_INVALID')
            data = RecoveryInput(str(incident.id), str(incident.tenant_id), str(incident.workflow_id),
                                 str(incident.integration_id), str(incident.id))
            if event.temporal_workflow_id != recovery_workflow_id(data.tenant_id, data.incident_id):
                raise ValueError('OUTBOX_WORKFLOW_ID_INVALID')
            return Claim(event.id, token, data, event.attempt_count + 1)

    def finish(self, claim: Claim, error_code: str | None = None):
        now = utcnow()
        values = {'lease_token': None, 'lease_expires_at': None, 'last_error': error_code}
        if error_code:
            values['next_attempt_at'] = now + timedelta(seconds=min(60, 2 ** min(claim.attempt_count, 6)))
        else:
            values['dispatched_at'] = now
        with self.sessions.begin() as db:
            return db.execute(update(RecoveryOutbox).where(
                RecoveryOutbox.id == claim.outbox_id, RecoveryOutbox.tenant_id == UUID(claim.data.tenant_id),
                RecoveryOutbox.incident_id == UUID(claim.data.incident_id),
                RecoveryOutbox.lease_token == claim.token, RecoveryOutbox.dispatched_at.is_(None),
            ).values(**values)).rowcount == 1

    async def dispatch_one(self) -> bool:
        claim = await asyncio.to_thread(self.claim)
        if claim is None:
            return False
        try:
            if self.client is None:
                self.client = await connect_temporal(self.settings)
            await start_recovery(self.client, claim.data, self.settings.temporal_task_queue)
        except Exception:
            acknowledged = await asyncio.to_thread(self.finish, claim, 'TEMPORAL_DISPATCH_FAILED')
            if acknowledged:
                log_event('dispatch_retry_scheduled', incident_id=claim.data.incident_id,
                          tenant_id=claim.data.tenant_id, attempt_count=claim.attempt_count,
                          error_code='TEMPORAL_DISPATCH_FAILED')
        else:
            acknowledged = await asyncio.to_thread(self.finish, claim)
            if acknowledged:
                log_event('recovery_dispatched', incident_id=claim.data.incident_id, tenant_id=claim.data.tenant_id)
        if not acknowledged:
            log_event('dispatch_acknowledgement_rejected', incident_id=claim.data.incident_id,
                      tenant_id=claim.data.tenant_id)
        return True


async def run_dispatcher():
    settings = Settings()
    engine = make_engine(settings.database_url.get_secret_value())
    dispatcher = OutboxDispatcher(session_factory(engine), settings)
    try:
        while True:
            try:
                work = await dispatcher.dispatch_one()
            except Exception:
                # A failed acknowledgement leaves the lease durable; another
                # dispatcher can reclaim it after expiry and deduplicate start.
                log_event('dispatcher_database_failure', error_code='OUTBOX_DATABASE_FAILURE')
                work = False
            await asyncio.sleep(0.1 if work else 2)
    finally:
        engine.dispose()


def main():
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_dispatcher())
    except KeyboardInterrupt:
        pass
    except Exception:
        log_event('dispatcher_stopped', error_code='DISPATCHER_STARTUP_FAILURE')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
