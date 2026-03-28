"""
Application configuration loaded from environment variables.

All environment-specific values must be declared here; do not read os.environ
directly elsewhere.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings."""

    app_env: str = "development"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = Field(
        ...,
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10

    openai_api_key: str = Field(..., description="OpenAI API key for LLM calls")
    ai_model: str = "gpt-4o"
    ai_max_tokens: int = 2048
    ai_temperature: float = 0.1
    max_daily_cost_usd: float = 10.0
    max_per_cv_cost_usd: float = 0.15

    shortlist_threshold: int = 80
    review_threshold: int = 50

    cors_allow_origins: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value: object) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return []


settings = Settings()
