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
