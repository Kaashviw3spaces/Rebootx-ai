from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SystemStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str = "ok"
    tenant_id: UUID
    tenant_name: str
    app_env: str
    recovery_mode: Literal["mock-only", "real_n8n"] = "mock-only"
    ai_provider: str
    ai_model: str
    temporal_task_queue: str


class DashboardSummaryResponse(BaseModel):
    total_incidents: int
    recovered_incidents: int
    needs_attention: int
    active_recovering: int
    recovery_rate: float
    rate_label: str = "Simulated Recovery Rate"
    mode: Literal["mock-only", "real_n8n"] = "mock-only"
    verified_real_recoveries: int = 0
    simulated_recoveries: int = 0
    ai_provider: str


class TrendPoint(BaseModel):
    date: str
    incidents_created: int
    incidents_recovered: int
    incidents_escalated: int


class IncidentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workflow_id: UUID
    workflow_external_id: str
    event_id: str
    source: str
    source_execution_id: str
    failed_step: str
    operation_id: str
    failure_type: str
    status: str
    event_timestamp: datetime
    created_at: datetime
    resolved_at: datetime | None
    recovery_reason: str | None
    verification_outcome: str | None
    recovery_mode: str = 'mock-only'
    diagnosis_summary: str | None = None
    diagnosis_source: str | None = None


class IncidentListResponse(BaseModel):
    items: list[IncidentItem]
    total: int
    limit: int
    offset: int


class WorkflowSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    external_id: str
    kind: str
    enabled: bool
    integration_id: UUID
    integration_kind: str
    incident_count: int
    last_incident_at: datetime | None
    latest_incident_status: str | None


class IntegrationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    enabled: bool
    workflow_count: int
    last_event_at: datetime | None


class ApprovalItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    incident_id: UUID
    workflow_external_id: str
    failed_step: str
    failure_type: str
    status: str
    escalation_reason: str | None
    requires_human_approval: bool
    recommended_action: str | None
    diagnosis_source: str | None
    created_at: datetime

