from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from decimal import Decimal
import math

from app.database import get_db
from app.models.enums import VerificationStatus, QualificationStatus, ManualReviewStatus
from app.schemas.website import WebsiteListResponse, WebsiteDetail, WebsiteSummary, WebsiteReviewUpdate
from app.schemas.traffic_metric import ManualTrafficCreate, TrafficMetricResponse
from app.schemas.common import PaginationMeta
from app.services.website_service import list_websites, get_website, update_manual_review
from app.services.traffic_service import add_manual_traffic

router = APIRouter(prefix="/websites", tags=["Websites"])

@router.get("", response_model=WebsiteListResponse)
def api_list_websites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verification_status: Optional[VerificationStatus] = Query(None),
    qualification_status: Optional[QualificationStatus] = Query(None),
    manual_review_status: Optional[ManualReviewStatus] = Query(None),
    country: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db)
):
    items, total = list_websites(
        db, page, page_size, verification_status, qualification_status,
        manual_review_status, country, language, is_active, search, sort_by, sort_order
    )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1
    )
    
    return WebsiteListResponse(items=items, pagination=pagination)

@router.get("/{website_id}", response_model=WebsiteDetail)
def api_get_website(website_id: UUID, db: Session = Depends(get_db)):
    website = get_website(db, website_id)
    return website

@router.patch("/{website_id}/review", response_model=WebsiteSummary)
def api_update_review(website_id: UUID, payload: WebsiteReviewUpdate, db: Session = Depends(get_db)):
    summary = update_manual_review(db, website_id, payload)
    return summary

@router.post("/{website_id}/traffic", response_model=TrafficMetricResponse, status_code=status.HTTP_201_CREATED)
def api_add_traffic(
    website_id: UUID, 
    payload: ManualTrafficCreate, 
    minimum_pageviews: Optional[Decimal] = Query(None, ge=0),
    db: Session = Depends(get_db)
):
    metric = add_manual_traffic(db, website_id, payload, minimum_pageviews)
    return TrafficMetricResponse.model_validate(metric)
