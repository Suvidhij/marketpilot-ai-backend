from functools import lru_cache
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "MarketPilot AI API"
    api_prefix: str = "/api/v1"
    cors_origins: list[HttpUrl] = Field(default_factory=lambda: [HttpUrl("http://localhost:3000")])


@lru_cache
def get_settings() -> Settings:
    return Settings()
