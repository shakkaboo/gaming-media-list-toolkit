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
    SEARCH_RESULTS_PER_QUERY: int = Field(10, ge=1, le=20)
    MAX_SEARCH_QUERIES: int = Field(20, ge=1, le=100)
    SEARCH_REQUEST_TIMEOUT_SECONDS: int = Field(10, gt=0)
    BRAVE_SEARCH_BASE_URL: str = "https://api.search.brave.com/res/v1/web/search"
    BRAVE_SEARCH_SAFESEARCH: str = "moderate"
    BRAVE_SEARCH_FRESHNESS: Optional[str] = None
    BRAVE_SEARCH_MAX_RETRIES: int = Field(2, ge=0, le=5)
    MAX_SEARCH_CONCURRENCY: int = Field(3, ge=1, le=10)

    MAX_URL_LENGTH: int = 2000
    MAX_HOST_LENGTH: int = 253
    ALLOW_NON_STANDARD_PORTS: bool = False
    MULTITENANT_HOSTING_DOMAINS: set[str] = {"substack.com", "wordpress.com", "blogspot.com"}

    TRAFFIC_PROVIDER: str = "mock"

    MAX_FETCH_CONCURRENCY: int = Field(5, gt=0)
    MAX_FETCHES_PER_HOST: int = Field(2, gt=0)
    FETCH_DNS_TIMEOUT_SECONDS: int = Field(3, gt=0)
    FETCH_CONNECT_TIMEOUT_SECONDS: int = Field(5, gt=0)
    FETCH_READ_TIMEOUT_SECONDS: int = Field(10, gt=0)
    FETCH_WRITE_TIMEOUT_SECONDS: int = Field(5, gt=0)
    FETCH_POOL_TIMEOUT_SECONDS: int = Field(5, gt=0)
    FETCH_TOTAL_TIMEOUT_SECONDS: int = Field(20, gt=0)
    MAX_FETCH_REDIRECTS: int = Field(5, ge=0, le=10)
    MAX_HTML_RESPONSE_BYTES: int = Field(2097152, gt=0)
    FETCH_PREVIEW_MAX_CHARS: int = Field(5000, gt=0)
    MAX_FETCH_CANDIDATES: int = Field(50, gt=0)
    FETCH_MAX_RETRIES: int = Field(2, ge=0, le=5)
    FETCH_RETRY_BASE_DELAY_SECONDS: float = Field(0.5, ge=0.0)
    FETCH_MAX_RETRY_DELAY_SECONDS: float = Field(3.0, ge=0.0)
    FETCH_USER_AGENT: str = Field("GamingMediaDiscoveryBot/0.1 (+local research tool)", min_length=1, max_length=200)
    
    MAX_VERIFICATION_CANDIDATES: int = Field(50, gt=0)
    MAX_VERIFICATION_CONCURRENCY: int = Field(4, gt=0)
    VERIFICATION_TIMEOUT_SECONDS: int = Field(5, gt=0)

    MAX_VERIFICATION_HTML_CHARS: int = Field(2000000, gt=0)
    MAX_ANALYZED_ANCHORS: int = Field(500, gt=0)
    MAX_ANALYZED_HEADINGS: int = Field(100, gt=0)
    MAX_ANALYZED_NAV_ITEMS: int = Field(150, gt=0)
    MAX_ANALYZED_TIME_ELEMENTS: int = Field(100, gt=0)
    MAX_ANALYZED_JSONLD_BLOCKS: int = Field(20, gt=0)
    MAX_JSONLD_BLOCK_CHARS: int = Field(50000, gt=0)
    MAX_JSONLD_DEPTH: int = Field(10, gt=0)
    MAX_EXTRACTED_TEXT_CHARS: int = Field(50000, gt=0)
    MAX_ELEMENT_TEXT_CHARS: int = Field(500, gt=0)
    MAX_REASON_EVIDENCE_CHARS: int = Field(300, gt=0)
    MAX_REASONS_PER_GROUP: int = Field(20, gt=0)

    GAMING_MEDIA_VERIFIED_THRESHOLD: int = Field(70, ge=0, le=100)
    GAMING_MEDIA_UNCERTAIN_THRESHOLD: int = Field(40, ge=0, le=100)
    DEFAULT_MINIMUM_PAGEVIEWS: int = 1000000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("MAX_FETCHES_PER_HOST")
    @classmethod
    def validate_host_concurrency(cls, v: int, info) -> int:
        max_c = info.data.get("MAX_FETCH_CONCURRENCY", 5)
        if v > max_c:
            raise ValueError("MAX_FETCHES_PER_HOST must not exceed MAX_FETCH_CONCURRENCY")
        return v
        
    @field_validator("FETCH_PREVIEW_MAX_CHARS")
    @classmethod
    def validate_preview_chars(cls, v: int, info) -> int:
        max_b = info.data.get("MAX_HTML_RESPONSE_BYTES", 2097152)
        if v >= max_b:
            raise ValueError("FETCH_PREVIEW_MAX_CHARS must be less than MAX_HTML_RESPONSE_BYTES")
        return v
        
    @field_validator("FETCH_MAX_RETRY_DELAY_SECONDS")
    @classmethod
    def validate_retry_delay(cls, v: float, info) -> float:
        base = info.data.get("FETCH_RETRY_BASE_DELAY_SECONDS", 0.5)
        if v < base:
            raise ValueError("FETCH_MAX_RETRY_DELAY_SECONDS must be >= FETCH_RETRY_BASE_DELAY_SECONDS")
        return v

    @field_validator("MAX_VERIFICATION_CONCURRENCY")
    @classmethod
    def validate_verification_concurrency(cls, v: int, info) -> int:
        max_c = info.data.get("MAX_VERIFICATION_CANDIDATES", 50)
        if v > max_c:
            raise ValueError("MAX_VERIFICATION_CONCURRENCY must not exceed MAX_VERIFICATION_CANDIDATES")
        return v

    @field_validator("GAMING_MEDIA_VERIFIED_THRESHOLD")
    @classmethod
    def validate_thresholds(cls, v: int, info) -> int:
        uncertain = info.data.get("GAMING_MEDIA_UNCERTAIN_THRESHOLD", 40)
        if not (0 <= uncertain < v <= 100):
            raise ValueError("Thresholds must satisfy 0 <= UNCERTAIN_THRESHOLD < VERIFIED_THRESHOLD <= 100")
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

    @field_validator("BRAVE_SEARCH_FRESHNESS")
    @classmethod
    def clean_freshness(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        return v.strip()

@lru_cache()
def get_settings() -> Settings:
    return Settings()
