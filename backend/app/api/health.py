from fastapi import APIRouter
from pydantic import BaseModel
from app.config import get_settings

router = APIRouter()
settings = get_settings()

class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str

class ConfigHealthResponse(BaseModel):
    environment: str
    search_provider: str
    traffic_provider: str
    verified_threshold: int
    uncertain_threshold: int
    default_minimum_pageviews: int

@router.get("/health", response_model=HealthResponse)
def get_health():
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        environment=settings.APP_ENV
    )

@router.get("/health/config", response_model=ConfigHealthResponse)
def get_config_health():
    return ConfigHealthResponse(
        environment=settings.APP_ENV,
        search_provider=settings.SEARCH_PROVIDER,
        traffic_provider=settings.TRAFFIC_PROVIDER,
        verified_threshold=settings.GAMING_MEDIA_VERIFIED_THRESHOLD,
        uncertain_threshold=settings.GAMING_MEDIA_UNCERTAIN_THRESHOLD,
        default_minimum_pageviews=settings.DEFAULT_MINIMUM_PAGEVIEWS
    )
