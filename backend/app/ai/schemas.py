import re
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

Category = Literal['NETWORK_ERROR', 'RATE_LIMIT', 'AUTHENTICATION_ERROR', 'INVALID_PAYLOAD',
                   'TIMEOUT', 'SERVICE_UNAVAILABLE', 'UNKNOWN_ERROR']
Action = Literal['RETRY_WITH_BACKOFF', 'WAIT_AND_RETRY', 'USE_APPROVED_FALLBACK', 'ESCALATE']
SAFE_FAILURE_CODES = frozenset({
    'TRANSIENT_NETWORK_FAILURE', 'NETWORK_RETRY_SUCCESS', 'PROVIDER_UNAVAILABLE',
    'NETWORK_FALLBACK_SUCCESS', 'NETWORK_BOTH_FAIL', 'NETWORK_VERIFY_FAIL',
    'RATE_LIMIT', 'AUTHENTICATION_FAILURE', 'INVALID_PAYLOAD', 'TIMEOUT',
    'NETWORK_ERROR', 'SERVICE_UNAVAILABLE', 'UNKNOWN_FAILURE',
    'CONNECTION_TIMEOUT', 'CONNECT_TIMEOUT', 'SCHEMA_VALIDATION_ERROR',
})


class DiagnosisInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    failure_code: str
    failure_timestamp: AwareDatetime
    integration_type: Literal['n8n', 'unknown'] = 'unknown'
    workflow_kind: Literal['notification_v1', 'unknown'] = 'unknown'
    http_status: int | None = Field(default=None, ge=100, le=599, strict=True)
    previous_attempts: list[Literal['MOCK_RETRY_SUCCEEDED', 'MOCK_RETRY_FAILED',
                                    'MOCK_FALLBACK_SUCCEEDED', 'MOCK_FALLBACK_FAILED', 'ESCALATED']] = Field(default_factory=list, max_length=10)

    @field_validator('failure_code')
    @classmethod
    def allowlisted_code(cls, value):
        return value if value in SAFE_FAILURE_CODES else 'UNKNOWN_FAILURE'

    @property
    def error_message(self):
        # Original webhook text is discarded. Only fixed codes/numeric evidence leave the server.
        return f'HTTP {self.http_status}: {self.failure_code}' if self.http_status else self.failure_code


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    failure_category: Category
    root_cause: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=1000)
    recommended_action: Action
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    requires_human_approval: bool
    alternative_actions: list[Action] = Field(max_length=4)

    @field_validator('root_cause', 'explanation')
    @classmethod
    def safe_text(cls, value):
        # Defense in depth: these fields are untrusted prose, never instructions.
        if re.search(r'https?://|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|'
                     r'\b(?:bearer|password|api[_ -]?key|access[_ -]?token|secret)\s*[:=]|'
                     r'\b(?:curl|powershell|cmd\.exe|rm -rf|drop table|delete from)\b|'
                     r'[A-Za-z0-9_+/=-]{32,}|[\x00-\x08\x0b-\x1f]', value, re.I):
            raise ValueError('UNSAFE_DIAGNOSIS_TEXT')
        return value
