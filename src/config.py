"""Application configuration loaded from environment variables at import time.

Any missing required variable raises a ValidationError immediately on startup
rather than surfacing as a runtime error mid-request.
"""

from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./backgrid.db"
    redis_url: str = "redis://localhost:6379"
    anthropic_api_key: Optional[str] = None
    enable_llm_extraction: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL must not be empty")
        return v


settings = Settings()
