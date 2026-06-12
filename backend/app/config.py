from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Gaming Media Discovery API"
    APP_ENV: str = "development"
    API_PREFIX: str = "/api"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/gaming_media"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    
    SEARCH_PROVIDER: str = "mock"
    BRAVE_SEARCH_API_KEY: Optional[str] = None
    TRAFFIC_PROVIDER: str = "mock"
    
    REQUEST_TIMEOUT_SECONDS: int = 10
    MAX_FETCH_CONCURRENCY: int = 5
    MAX_RESPONSE_BYTES: int = 5242880
    
    GAMING_MEDIA_VERIFIED_THRESHOLD: int = 70
    GAMING_MEDIA_UNCERTAIN_THRESHOLD: int = 40
    DEFAULT_MINIMUM_PAGEVIEWS: int = 1000000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("GAMING_MEDIA_VERIFIED_THRESHOLD")
    @classmethod
    def validate_thresholds(cls, v: int, info) -> int:
        uncertain = info.data.get("GAMING_MEDIA_UNCERTAIN_THRESHOLD", 40)
        if v <= uncertain:
            raise ValueError("VERIFIED_THRESHOLD must be greater than UNCERTAIN_THRESHOLD")
        return v

    @field_validator("REQUEST_TIMEOUT_SECONDS", "MAX_FETCH_CONCURRENCY", "MAX_RESPONSE_BYTES")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Numeric limits must be positive")
        return v

    @field_validator("DEFAULT_MINIMUM_PAGEVIEWS")
    @classmethod
    def validate_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Minimum pageviews must be non-negative")
        return v
        
    @field_validator("BRAVE_SEARCH_API_KEY")
    @classmethod
    def validate_brave_key(cls, v: Optional[str], info) -> Optional[str]:
        provider = info.data.get("SEARCH_PROVIDER", "mock")
        if provider == "brave" and not v:
            raise ValueError("BRAVE_SEARCH_API_KEY is required when SEARCH_PROVIDER is brave")
        return v

@lru_cache()
def get_settings() -> Settings:
    return Settings()
