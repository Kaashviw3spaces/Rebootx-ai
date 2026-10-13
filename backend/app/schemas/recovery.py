from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class TimelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor: str
    event_type: str
    redacted_details: dict
    occurred_at: datetime
