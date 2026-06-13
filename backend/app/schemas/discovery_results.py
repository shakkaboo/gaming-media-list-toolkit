from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class DiscoveryWebsiteResult(BaseModel):
    website_id: UUID
    name: Optional[str] = None
    domain: str
    homepage_url: str
    canonical_key: str
    is_multitenant: bool
    verification_status: Optional[str] = None
    verification_score: Optional[float] = None
    confidence: Optional[float] = None
    activity_status: Optional[str] = None
    detected_categories: List[str] = []
    classifier_version: Optional[str] = None
    qualification_status: Optional[str] = None
    estimated_monthly_pageviews: Optional[float] = None
    traffic_provider: Optional[str] = None
    traffic_confidence: Optional[float] = None
    source_count: int
    source_queries: List[str]
    latest_verified_at: Optional[datetime] = None

class DiscoveryResultsResponse(BaseModel):
    job_id: UUID
    job_status: str
    page: int
    page_size: int
    total: int
    items: List[DiscoveryWebsiteResult]
