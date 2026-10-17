from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

Reference = Annotated[str, StringConstraints(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:/-]+$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetails(StrictModel):
    category: Annotated[str, StringConstraints(min_length=1, max_length=100, pattern=r"^[A-Z0-9_]+$")]
    message: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    http_status: int | None = Field(default=None, ge=100, le=599, strict=True)


class FailureEvent(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: Reference
    timestamp: AwareDatetime
    source: Literal["n8n"]
    source_execution_id: Reference
    workflow_external_id: Reference
    failed_step: Reference
    operation_id: Reference
    error: ErrorDetails


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workflow_id: UUID
    event_id: str
    source: str
    source_execution_id: str
    failed_step: str
    operation_id: str
    failure_type: str
    error_details: dict
    status: str
    event_timestamp: datetime
    created_at: datetime
    recovery_mode: str = 'mock-only'
    verification_outcome: str | None = None
    recovery_reason: str | None = None


class IngestionResponse(BaseModel):
    incident_id: UUID
    status: str
    duplicate: bool
