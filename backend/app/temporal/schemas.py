"""Versioned Temporal payloads: identifiers and fixed codes, never credentials."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryInput:
    incident_id: str
    tenant_id: str
    workflow_id: str
    integration_id: str
    correlation_id: str
    version: int = 1


@dataclass(frozen=True)
class StepRequest:
    recovery: RecoveryInput
    operation: str
    reason: str = ''


@dataclass(frozen=True)
class StepResult:
    state: str
    category: str = ''
    success: bool = False
    reason: str = ''
    delay_seconds: int = 0


def recovery_workflow_id(tenant_id, incident_id) -> str:
    return f'rebootx:recovery:v1:{tenant_id}:{incident_id}'
