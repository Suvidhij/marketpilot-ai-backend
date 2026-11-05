from functools import lru_cache
from typing import Literal
from pydantic import Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    app_name: str = "MarketPilot AI API"
    api_prefix: str = "/api/v1"
    environment: Literal["development", "production", "test"] = "development"
    database_url: str = "sqlite:///./marketpilot.db"
    cors_origins: list[HttpUrl] = Field(
        default_factory=lambda: [HttpUrl("http://localhost:3000")]
    )
    cookie_secure: bool = False
    session_hours: int = Field(default=24, ge=1, le=168)
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    ai_enabled: bool = False
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver", "backend"]

    @model_validator(mode="after")
    def production_rules(self):
        if self.environment == "production":
            if not self.cookie_secure or "*" in self.allowed_hosts:
                raise ValueError(
                    "Production requires secure cookies and explicit allowed hosts"
                )
            if any(origin.scheme != "https" for origin in self.cors_origins):
                raise ValueError("Production frontend origins must use HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
