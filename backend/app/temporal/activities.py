from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.ai.diagnosis import DiagnosisEngine
from app.core.config import Settings
from app.services.diagnosis import diagnosis_evidence
from app.services.recovery import RecoveryDenied, apply_step
from app.services.recovery import scoped_incident
from app.services.real_n8n import real_step
from app.integrations.n8n.client import N8nClient
from app.temporal.logging import log_event
from app.temporal.schemas import StepRequest, StepResult


class RecoveryActivities:
    def __init__(self, sessions, settings=None, diagnosis_engine=None, n8n_client_factory=N8nClient):
        self.sessions = sessions
        self.n8n_client_factory = n8n_client_factory
        # Default construction remains deterministic for existing SDK/unit test callers.
        self.settings = settings if settings is not None else Settings(_env_file=None, ai_provider='mock')
        self.diagnosis_engine = diagnosis_engine if diagnosis_engine is not None else DiagnosisEngine(self.settings)

    @activity.defn(name='recovery_step')
    def step(self, request: StepRequest) -> StepResult:
        try:
            with self.sessions() as db:
                incident = scoped_incident(db, request, lock=False)
                mode = incident.recovery_mode
            if mode == 'real_n8n' and request.operation in {'retry', 'fallback', 'verify', 'recover', 'escalate'}:
                return real_step(self.sessions, request, self.settings, self.n8n_client_factory)
            diagnosis = None
            if request.operation == 'diagnose':
                evidence = diagnosis_evidence(self.sessions, request)
                if evidence is not None:
                    budget = activity.info().start_to_close_timeout
                    # Old histories can still schedule 30s activities: leave DB headroom there too.
                    timeout = max(1, budget.total_seconds() - 10) if budget is not None else None
                    diagnosis = self.diagnosis_engine.diagnose(evidence, timeout_seconds=timeout)
            with self.sessions.begin() as db:
                if db.bind.dialect.name == 'sqlite':
                    # SQLite ignores FOR UPDATE. Reserve the write transaction
                    # before reading idempotency records, matching PG row locks.
                    db.connection().exec_driver_sql('BEGIN IMMEDIATE')
                result = apply_step(db, request, diagnosis, self.settings)
        except RecoveryDenied as exc:
            raise ApplicationError(str(exc), type='RecoveryDenied', non_retryable=True) from None
        except Exception:
            # SQLAlchemy exceptions may contain URLs or SQL parameter values.
            raise ApplicationError('RECOVERY_DATABASE_FAILURE', type='RecoveryDatabaseFailure') from None
        log_event('recovery_step_completed', incident_id=request.recovery.incident_id,
                  tenant_id=request.recovery.tenant_id, operation=request.operation, state=result.state)
        return result
