from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.services.recovery import RecoveryDenied, apply_step
from app.temporal.logging import log_event
from app.temporal.schemas import StepRequest, StepResult


class RecoveryActivities:
    def __init__(self, sessions):
        self.sessions = sessions

    @activity.defn(name='recovery_step')
    def step(self, request: StepRequest) -> StepResult:
        try:
            with self.sessions.begin() as db:
                if db.bind.dialect.name == 'sqlite':
                    # SQLite ignores FOR UPDATE. Reserve the write transaction
                    # before reading idempotency records, matching PG row locks.
                    db.connection().exec_driver_sql('BEGIN IMMEDIATE')
                result = apply_step(db, request)
        except RecoveryDenied as exc:
            raise ApplicationError(str(exc), type='RecoveryDenied', non_retryable=True) from None
        except Exception:
            # SQLAlchemy exceptions may contain URLs or SQL parameter values.
            raise ApplicationError('RECOVERY_DATABASE_FAILURE', type='RecoveryDatabaseFailure') from None
        log_event('recovery_step_completed', incident_id=request.recovery.incident_id,
                  tenant_id=request.recovery.tenant_id, operation=request.operation, state=result.state)
        return result
