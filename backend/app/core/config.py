from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from uuid import UUID


class N8nAuthorization(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    integration_id: UUID
    workflow_external_id: str
    operation: str = 'retry_execution'
    idempotent: bool = False
    side_effect_safe: bool = False
    workflow_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://rebootx:local-dev-only@localhost:5432/rebootx"
    )
    app_env: str = "development"
    recovery_mode: Literal['mock-only', 'real_n8n'] = 'mock-only'
    n8n_base_url: str = 'http://127.0.0.1:5678'
    n8n_api_key: SecretStr = SecretStr('')
    n8n_supported_version: str = ''
    n8n_authorizations: list[N8nAuthorization] = Field(default_factory=list)
    n8n_connect_timeout: float = Field(default=2, ge=0.1, le=5)
    n8n_read_timeout: float = Field(default=5, ge=0.1, le=10)
    n8n_verification_seconds: float = Field(default=15, ge=0, le=20)
    webhook_timestamp_tolerance_seconds: int = Field(default=300, ge=1, le=3600)
    max_webhook_body_bytes: int = Field(default=65536, ge=1024, le=1048576)
    temporal_address: str = '127.0.0.1:7233'
    temporal_namespace: str = 'default'
    temporal_task_queue: str = 'rebootx-recovery-v1'
    temporal_api_key: SecretStr = SecretStr('')
    temporal_tls_enabled: bool = False
    ai_provider: Literal['mock', 'gemma'] = 'mock'
    ai_model: Literal['gemma-4-26b-a4b-it', 'gemma-4-31b-it'] = 'gemma-4-26b-a4b-it'
    gemini_api_key: SecretStr = SecretStr('')
    ai_timeout_seconds: float = Field(default=60, ge=1, le=60, allow_inf_nan=False)
    ai_fallback_enabled: bool = True
    ai_min_confidence: float = Field(default=0.75, ge=0, le=1)
    ai_fast_path_enabled: bool = True
    ai_max_output_tokens: int = Field(default=1024, ge=512, le=2048)
    ai_thinking_level: Literal['default', 'minimal', 'high'] = 'default'
