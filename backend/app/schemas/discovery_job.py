from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from app.models.enums import DiscoveryJobStatus
from app.schemas.common import PaginationMeta

class DiscoveryJobCreate(BaseModel):
    target_market: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    categories: List[str] = Field(..., min_length=1)
    minimum_pageviews: int = Field(0, ge=0)
    maximum_queries: int = Field(10, ge=1, le=100)
    results_per_query: int = Field(10, ge=1, le=50)

    @field_validator('target_market', 'language')
    def trim_and_check_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Value cannot be blank")
        return trimmed

    @field_validator('categories')
    def clean_categories(cls, v: List[str]) -> List[str]:
        cleaned = []
        seen_lower = set()
        for cat in v:
            trimmed = cat.strip()
            if trimmed:
                lower = trimmed.lower()
                if lower not in seen_lower:
                    seen_lower.add(lower)
                    cleaned.append(trimmed)
        if not cleaned:
            raise ValueError("Must contain at least one non-blank category")
        return cleaned

class DiscoveryJobSummary(BaseModel):
    id: UUID
    status: DiscoveryJobStatus
    target_market: str
    language: str
    categories: List[str]
    minimum_pageviews: int
    attempt_number: int
    queries_generated: int
    queries_completed: int
    candidates_found: int
    sites_verified: int
    websites_uncertain: int
    sites_rejected: int
    sites_qualified: int
    sites_upcoming: int
    sites_traffic_missing: int
    contacts_found: int
    errors_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class DiscoveryJobDetail(DiscoveryJobSummary):
    maximum_queries: int
    results_per_query: int
    search_provider: str
    traffic_provider: str
    duplicates_removed: int
    candidates_filtered: int
    sites_fetched: int
    failure_message: Optional[str] = None
    updated_at: datetime

class DiscoveryJobListResponse(BaseModel):
    items: List[DiscoveryJobSummary]
    pagination: PaginationMeta
