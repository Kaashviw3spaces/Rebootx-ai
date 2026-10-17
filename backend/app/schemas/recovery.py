from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str
    failure_category: str
    root_cause: str
    explanation: str
    recommended_action: str
    confidence: float
    requires_human_approval: bool
    alternative_actions: list[str]
    provider: str
    source: str
    model_id: str
    requested_model_id: str
    diagnosed_at: datetime
    fallback_reason: str | None
    policy_reason: str


class RecoveryResponse(BaseModel):
    incident_id: UUID
    status: str
    mode: str = 'mock-only'
    verification_outcome: str | None
    escalation_reason: str | None
    temporal_workflow_id: str | None
    dispatch_status: str
    dispatch_attempts: int
    dispatch_error: str | None
    diagnosis: DiagnosisResponse | None = None
    provider: str = 'n8n'
    external_execution_id: str | None = None
    evidence: dict | None = None


class AttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    action: str
    adapter: str | None
    outcome: str | None
    failure_reason: str | None
    external_reference: str | None
    started_at: datetime
    ended_at: datetime | None
    evidence: dict | None = None


class TimelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor: str
    event_type: str
    redacted_details: dict
    occurred_at: datetime
