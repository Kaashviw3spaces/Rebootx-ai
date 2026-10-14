from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://rebootx:local-dev-only@localhost:5432/rebootx"
    )
    app_env: str = "development"
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
