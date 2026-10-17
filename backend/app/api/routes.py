from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select

from app.core.security import authenticate_reader, authenticate_webhook
from app.models.entities import Incident, IncidentDiagnosis, Integration, RecoveryAttempt, AuditLog, RecoveryOutbox, Workflow
from app.schemas.dashboard import (
    ApprovalItemResponse,
    DashboardSummaryResponse,
    IncidentItem,
    IncidentListResponse,
    IntegrationSummaryResponse,
    SystemStatusResponse,
    TrendPoint,
    WorkflowSummaryResponse,
)
from app.schemas.events import FailureEvent, IncidentResponse, IngestionResponse
from app.services.incidents import receive_failure
from app.schemas.recovery import RecoveryResponse, AttemptResponse, TimelineResponse

router = APIRouter()


def get_db(request: Request):
    with request.app.state.sessions() as db:
        yield db


@router.get("/health")
def health():
    # Liveness only; migrations and DB connectivity are separate checks.
    return {"status": "ok"}


@router.post("/mock/primary-provider-failure", status_code=503)
def mock_primary_provider_failure(request: Request):
    # Demo endpoint for n8n workflows to simulate a downstream provider outage.
    if request.app.state.settings.app_env not in {"development", "demo", "test"}:
        raise HTTPException(404, "Endpoint not found")
    raise HTTPException(503, "Primary notification provider unavailable (simulated outage)")


@router.post("/api/v1/events/failure", status_code=202, response_model=IngestionResponse)
async def failure(request: Request, db=Depends(get_db)):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > request.app.state.settings.max_webhook_body_bytes:
            raise HTTPException(413, "Event body too large")
    integration, _ = authenticate_webhook(
        db, request.headers.get("X-Integration-ID"), request.headers.get("X-Webhook-Signature"), bytes(raw),
    )
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "Expected application/json")
    try:
        event = FailureEvent.model_validate_json(bytes(raw))
    except ValidationError:
        # Never echo the untrusted payload or validation input back to a caller.
        raise HTTPException(422, "Malformed failure event") from None
    age = abs((datetime.now(timezone.utc) - event.timestamp).total_seconds())
    if age > request.app.state.settings.webhook_timestamp_tolerance_seconds:
        raise HTTPException(401, "Event timestamp outside allowed tolerance")
    incident, duplicate = receive_failure(db, integration, event, request.app.state.settings.recovery_mode)
    return IngestionResponse(incident_id=incident.id, status=incident.status, duplicate=duplicate)


@router.get("/api/v1/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: UUID, request: Request, db=Depends(get_db)):
    return authorized_incident(db, request, incident_id)


def authorized_incident(db, request, incident_id):
    tenant = authenticate_reader(db, request.headers.get("Authorization"))
    incident = db.scalar(select(Incident).where(Incident.id == incident_id, Incident.tenant_id == tenant.id))
    if incident is None:
        raise HTTPException(404, "Incident not found")
    return incident


@router.get('/api/v1/incidents/{incident_id}/recovery', response_model=RecoveryResponse)
def get_recovery(incident_id: UUID, request: Request, db=Depends(get_db)):
    incident = authorized_incident(db, request, incident_id)
    outbox = db.scalar(select(RecoveryOutbox).where(
        RecoveryOutbox.tenant_id == incident.tenant_id, RecoveryOutbox.incident_id == incident.id))
    diagnosis = db.scalar(select(IncidentDiagnosis).where(
        IncidentDiagnosis.tenant_id == incident.tenant_id, IncidentDiagnosis.incident_id == incident.id))
    external = db.scalar(select(RecoveryAttempt).where(
        RecoveryAttempt.tenant_id == incident.tenant_id, RecoveryAttempt.incident_id == incident.id,
        RecoveryAttempt.adapter == 'n8n-public-api-v1'))
    return RecoveryResponse(
        incident_id=incident.id, status=incident.status,
        mode=incident.recovery_mode,
        external_execution_id=external.external_reference if external else None,
        evidence=external.evidence if external else None,
        verification_outcome=incident.verification_outcome, escalation_reason=incident.recovery_reason,
        temporal_workflow_id=outbox.temporal_workflow_id if outbox else None,
        dispatch_status=('DISPATCHED' if outbox.dispatched_at else 'PENDING') if outbox else 'NOT_QUEUED',
        dispatch_attempts=outbox.attempt_count if outbox else 0,
        dispatch_error=outbox.last_error if outbox else None,
        diagnosis=diagnosis,
    )


@router.get('/api/v1/incidents/{incident_id}/attempts', response_model=list[AttemptResponse])
def get_attempts(incident_id: UUID, request: Request, db=Depends(get_db)):
    incident = authorized_incident(db, request, incident_id)
    return db.scalars(select(RecoveryAttempt).where(
        RecoveryAttempt.tenant_id == incident.tenant_id, RecoveryAttempt.incident_id == incident.id,
    ).order_by(RecoveryAttempt.started_at, RecoveryAttempt.id)).all()


@router.get('/api/v1/incidents/{incident_id}/timeline', response_model=list[TimelineResponse])
def get_timeline(incident_id: UUID, request: Request, db=Depends(get_db)):
    incident = authorized_incident(db, request, incident_id)
    return db.scalars(select(AuditLog).where(
        AuditLog.tenant_id == incident.tenant_id, AuditLog.incident_id == incident.id,
    ).order_by(AuditLog.occurred_at, AuditLog.id)).all()


@router.get("/api/v1/system/status", response_model=SystemStatusResponse)
def get_system_status(request: Request, db=Depends(get_db)):
    tenant = authenticate_reader(db, request.headers.get("Authorization"))
    settings = request.app.state.settings
    return SystemStatusResponse(
        status="ok",
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        app_env=settings.app_env,
        recovery_mode=settings.recovery_mode,
        ai_provider=settings.ai_provider,
        ai_model=settings.ai_model,
        temporal_task_queue=settings.temporal_task_queue,
    )


@router.get("/api/v1/dashboard/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(request: Request, db=Depends(get_db)):
    tenant = authenticate_reader(db, request.headers.get("Authorization"))
    total = db.scalar(select(func.count(Incident.id)).where(Incident.tenant_id == tenant.id)) or 0
    recovered = db.scalar(select(func.count(Incident.id)).where(
        Incident.tenant_id == tenant.id, Incident.status == "RECOVERED"
    )) or 0
    needs_attention = db.scalar(select(func.count(Incident.id)).where(
        Incident.tenant_id == tenant.id, Incident.status == "NEEDS_ATTENTION"
    )) or 0
    active = db.scalar(select(func.count(Incident.id)).where(
        Incident.tenant_id == tenant.id,
        Incident.status.in_(["VALIDATING", "DIAGNOSING", "PLANNED", "EXECUTING", "VERIFYING", "RECEIVED"])
    )) or 0
    rate = round((recovered / total) * 100, 1) if total > 0 else 0.0
    real = db.scalar(select(func.count(Incident.id)).where(Incident.tenant_id == tenant.id,
        Incident.status == 'RECOVERED', Incident.verification_outcome == 'REAL_RECOVERY_VERIFIED')) or 0
    return DashboardSummaryResponse(
        total_incidents=total,
        recovered_incidents=recovered,
        needs_attention=needs_attention,
        active_recovering=active,
        recovery_rate=rate,
        rate_label="Simulated Recovery Rate" if request.app.state.settings.recovery_mode == 'mock-only' and not real else "Recovery Rate (see mode breakdown)",
        mode=request.app.state.settings.recovery_mode,
        verified_real_recoveries=real,
        simulated_recoveries=recovered - real,
        ai_provider=request.app.state.settings.ai_provider,
    )


@router.get("/api/v1/dashboard/trends", response_model=list[TrendPoint])
def get_dashboard_trends(request: Request, days: int = Query(default=7, ge=1, le=30), db=Depends(get_db)):
    tenant = authenticate_reader(db, request.headers.get("Authorization"))
    now = datetime.now(timezone.utc)
    date_keys = [(now - timedelta(days=d)).strftime("%Y-%m-%d") for d in reversed(range(days))]
    counts = {k: {"created": 0, "recovered": 0, "escalated": 0} for k in date_keys}

    window_start = datetime.combine(now.date() - timedelta(days=days - 1), datetime.min.time(), tzinfo=timezone.utc)
    incidents = db.scalars(select(Incident).where(
        Incident.tenant_id == tenant.id, Incident.created_at >= window_start
    )).all()

    for inc in incidents:
        c_at = inc.created_at
        if c_at.tzinfo is None:
            c_at = c_at.replace(tzinfo=timezone.utc)
        k = c_at.strftime("%Y-%m-%d")
        if k in counts:
            counts[k]["created"] += 1
            if inc.status == "RECOVERED":
                counts[k]["recovered"] += 1
            elif inc.status == "NEEDS_ATTENTION":
                counts[k]["escalated"] += 1

    return [
        TrendPoint(
            date=k,
            incidents_created=counts[k]["created"],
            incidents_recovered=counts[k]["recovered"],
            incidents_escalated=counts[k]["escalated"],
        )
        for k in date_keys
    ]


@router.get("/api/v1/incidents", response_model=IncidentListResponse)
def list_incidents(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    failure_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db=Depends(get_db),
):
    tenant = authenticate_reader(db, request.headers.get("Authorization"))
    conditions = [Incident.tenant_id == tenant.id]
    if status:
        conditions.append(Incident.status == status)
    if failure_type:
        conditions.append(Incident.failure_type == failure_type)
    if search:
        s = f"%{search.strip()}%"
        conditions.append(or_(
            Incident.operation_id.ilike(s),
            Incident.source_execution_id.ilike(s),
            Incident.failed_step.ilike(s),
            Incident.event_id.ilike(s),
            Workflow.external_id.ilike(s),
        ))

    total = db.scalar(
        select(func.count(Incident.id))
        .join(Workflow, Workflow.id == Incident.workflow_id)
        .where(and_(*conditions))
    ) or 0

    query = (
        select(
            Incident,
            Workflow.external_id,
            IncidentDiagnosis.root_cause,
            IncidentDiagnosis.model_id,
            IncidentDiagnosis.provider,
            IncidentDiagnosis.status.label("diag_status"),
        )
        .join(Workflow, Workflow.id == Incident.workflow_id)
        .outerjoin(IncidentDiagnosis, and_(
            IncidentDiagnosis.tenant_id == Incident.tenant_id,
            IncidentDiagnosis.incident_id == Incident.id,
        ))
        .where(and_(*conditions))
        .order_by(Incident.created_at.desc(), Incident.id.desc())
        .offset(offset)
        .limit(limit)
    )

    rows = db.execute(query).all()
    items = []
    for inc, wf_ext_id, root_cause, model_id, provider, diag_status in rows:
        diag_source = None
        if diag_status in {"MOCK", "FALLBACK", "FAILED"} or model_id == "mock-diagnosis-v1":
            diag_source = "mock"
        elif model_id == "deterministic-diagnosis-v1":
            diag_source = "deterministic"
        elif provider:
            diag_source = provider

        items.append(IncidentItem(
            id=inc.id,
            workflow_id=inc.workflow_id,
            workflow_external_id=wf_ext_id,
            event_id=inc.event_id,
            source=inc.source,
            source_execution_id=inc.source_execution_id,
            failed_step=inc.failed_step,
            operation_id=inc.operation_id,
            failure_type=inc.failure_type,
            status=inc.status,
            event_timestamp=inc.event_timestamp,
            created_at=inc.created_at,
            resolved_at=inc.resolved_at,
            recovery_reason=inc.recovery_reason,
            verification_outcome=inc.verification_outcome,
            recovery_mode=inc.recovery_mode,
            diagnosis_summary=root_cause,
            diagnosis_source=diag_source,
        ))

    return IncidentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/api/v1/workflows", response_model=list[WorkflowSummaryResponse])
def list_workflows(request: Request, db=Depends(get_db)):
    tenant = authenticate_reader(db, request.headers.get("Authorization"))
    workflows = db.execute(
        select(Workflow, Integration.kind.label("integration_kind"))
        .join(Integration, Integration.id == Workflow.integration_id)
        .where(Workflow.tenant_id == tenant.id)
        .order_by(Workflow.external_id)
    ).all()

    inc_stats_raw = db.execute(
        select(
            Incident.workflow_id,
            func.count(Incident.id).label("cnt"),
            func.max(Incident.created_at).label("last_at"),
        )
        .where(Incident.tenant_id == tenant.id)
        .group_by(Incident.workflow_id)
    ).all()
    inc_stats = {r[0]: (r[1], r[2]) for r in inc_stats_raw}

    results = []
    for wf, integration_kind in workflows:
        latest_status = db.scalar(
            select(Incident.status)
            .where(Incident.tenant_id == tenant.id, Incident.workflow_id == wf.id)
            .order_by(Incident.created_at.desc(), Incident.id.desc())
            .limit(1)
        )
        count, last_at = inc_stats.get(wf.id, (0, None))
        results.append(WorkflowSummaryResponse(
            id=wf.id,
            external_id=wf.external_id,
            kind=wf.kind,
            enabled=wf.enabled,
            integration_id=wf.integration_id,
            integration_kind=integration_kind,
            incident_count=count,
            last_incident_at=last_at,
            latest_incident_status=latest_status,
        ))
    return results


@router.get("/api/v1/integrations", response_model=list[IntegrationSummaryResponse])
def list_integrations(request: Request, db=Depends(get_db)):
    tenant = authenticate_reader(db, request.headers.get("Authorization"))
    integrations = db.scalars(
        select(Integration).where(Integration.tenant_id == tenant.id).order_by(Integration.id)
    ).all()

    wf_counts = dict(db.execute(
        select(Workflow.integration_id, func.count(Workflow.id))
        .where(Workflow.tenant_id == tenant.id)
        .group_by(Workflow.integration_id)
    ).all())

    last_events = dict(db.execute(
        select(Incident.integration_id, func.max(Incident.created_at))
        .where(Incident.tenant_id == tenant.id)
        .group_by(Incident.integration_id)
    ).all())

    return [
        IntegrationSummaryResponse(
            id=integ.id,
            kind=integ.kind,
            enabled=integ.enabled,
            workflow_count=wf_counts.get(integ.id, 0),
            last_event_at=last_events.get(integ.id),
        )
        for integ in integrations
    ]


@router.get("/api/v1/approvals", response_model=list[ApprovalItemResponse])
def list_approvals(request: Request, db=Depends(get_db)):
    tenant = authenticate_reader(db, request.headers.get("Authorization"))
    rows = db.execute(
        select(
            Incident,
            Workflow.external_id,
            IncidentDiagnosis.requires_human_approval,
            IncidentDiagnosis.recommended_action,
            IncidentDiagnosis.model_id,
            IncidentDiagnosis.provider,
            IncidentDiagnosis.status.label("diag_status"),
        )
        .join(Workflow, Workflow.id == Incident.workflow_id)
        .outerjoin(IncidentDiagnosis, and_(
            IncidentDiagnosis.tenant_id == Incident.tenant_id,
            IncidentDiagnosis.incident_id == Incident.id,
        ))
        .where(
            Incident.tenant_id == tenant.id,
            or_(
                Incident.status == "NEEDS_ATTENTION",
                IncidentDiagnosis.requires_human_approval.is_(True),
            ),
        )
        .order_by(Incident.created_at.desc(), Incident.id.desc())
    ).all()

    items = []
    for inc, wf_ext_id, req_approval, rec_action, model_id, provider, diag_status in rows:
        diag_source = None
        if diag_status in {"MOCK", "FALLBACK", "FAILED"} or model_id == "mock-diagnosis-v1":
            diag_source = "mock"
        elif model_id == "deterministic-diagnosis-v1":
            diag_source = "deterministic"
        elif provider:
            diag_source = provider

        items.append(ApprovalItemResponse(
            incident_id=inc.id,
            workflow_external_id=wf_ext_id,
            failed_step=inc.failed_step,
            failure_type=inc.failure_type,
            status=inc.status,
            escalation_reason=inc.recovery_reason,
            requires_human_approval=bool(req_approval),
            recommended_action=rec_action,
            diagnosis_source=diag_source,
            created_at=inc.created_at,
        ))
    return items
