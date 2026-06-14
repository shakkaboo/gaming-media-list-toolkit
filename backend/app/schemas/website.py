from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from app.models.enums import VerificationStatus, QualificationStatus, ManualReviewStatus, ContactType
from app.schemas.common import PaginationMeta
from app.schemas.traffic_metric import TrafficMetricResponse
from app.schemas.contact import ContactResponse
from app.schemas.website_verification import WebsiteVerificationResponse
from app.schemas.discovery_source import DiscoverySourceResponse
from app.schemas.processing_error import ProcessingErrorResponse

class WebsiteSummary(BaseModel):
    id: UUID
    domain: str
    homepage_url: str
    name: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    categories: Optional[List[Any]] = None
    current_verification_status: VerificationStatus
    current_qualification_status: QualificationStatus
    manual_review_status: ManualReviewStatus
    is_active: bool
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Computed fields not on the base ORM model directly
    latest_metric_type: Optional[str] = None
    latest_monthly_visits: Optional[Decimal] = None
    latest_pages_per_visit: Optional[Decimal] = None
    latest_monthly_pageviews: Optional[Decimal] = None
    latest_estimated_pageviews: Optional[Decimal] = None
    latest_growth_rate: Optional[Decimal] = None
    latest_traffic_provider: Optional[str] = None
    latest_evidence_url: Optional[str] = None
    latest_traffic_recorded_at: Optional[datetime] = None
    best_contact_email: Optional[str] = None
    best_contact_type: Optional[ContactType] = None
    effective_review_decision: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class WebsiteReviewUpdate(BaseModel):
    manual_review_status: ManualReviewStatus

class WebsiteDetail(WebsiteSummary):
    verification_history: List[WebsiteVerificationResponse] = []
    traffic_history: List[TrafficMetricResponse] = []
    contacts: List[ContactResponse] = []
    discovery_sources: List[DiscoverySourceResponse] = []
    recent_processing_errors: List[ProcessingErrorResponse] = []

class WebsiteListResponse(BaseModel):
    items: List[WebsiteSummary]
    pagination: PaginationMeta
