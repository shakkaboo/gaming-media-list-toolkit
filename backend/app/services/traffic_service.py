from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from uuid import UUID
import logging
from typing import Optional

from app.models.enums import VerificationStatus, QualificationStatus
from app.models.website import Website
from app.models.traffic_metric import TrafficMetric
from app.schemas.traffic_metric import ManualTrafficCreate
from app.exceptions import ResourceNotFoundError, InvalidOperationError
from app.config import get_settings

logger = logging.getLogger(__name__)

def calculate_estimated_pageviews(monthly_visits: Decimal, pages_per_visit: Decimal) -> Decimal:
    """Calculate estimated pageviews carefully without floats."""
    if monthly_visits < 0 or pages_per_visit < 0:
        raise ValueError("Traffic inputs cannot be negative")
    
    result = monthly_visits * pages_per_visit
    return result.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def determine_qualification_status(
    estimated_pageviews: Optional[Decimal],
    verification_status: VerificationStatus,
    minimum_pageviews: Decimal
) -> QualificationStatus:
    """Determine qualification status strictly following the hierarchy rules."""
    if verification_status == VerificationStatus.rejected:
        return QualificationStatus.rejected
    if verification_status in (VerificationStatus.uncertain, VerificationStatus.fetch_failed):
        return QualificationStatus.needs_review
    
    if estimated_pageviews is None:
        return QualificationStatus.traffic_missing
        
    if estimated_pageviews > minimum_pageviews:
        return QualificationStatus.qualified
        
    return QualificationStatus.upcoming

def add_manual_traffic(
    db: Session,
    website_id: UUID,
    payload: ManualTrafficCreate,
    minimum_pageviews: Optional[Decimal] = None
) -> TrafficMetric:
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise ResourceNotFoundError("Website not found")
        
    try:
        estimated_pageviews = calculate_estimated_pageviews(payload.monthly_visits, payload.pages_per_visit)
    except ValueError as e:
        raise InvalidOperationError(str(e))
        
    metric = TrafficMetric(
        website_id=website.id,
        provider='manual',
        monthly_visits=payload.monthly_visits,
        pages_per_visit=payload.pages_per_visit,
        estimated_pageviews=estimated_pageviews,
        growth_rate=payload.growth_rate,
        measurement_month=payload.measurement_month,
        confidence=payload.confidence,
        is_manual=True,
        notes=payload.notes
    )
    
    db.add(metric)
    
    threshold = minimum_pageviews if minimum_pageviews is not None else Decimal(get_settings().DEFAULT_MINIMUM_PAGEVIEWS)
    
    new_qual_status = determine_qualification_status(
        estimated_pageviews=estimated_pageviews,
        verification_status=website.current_verification_status,
        minimum_pageviews=threshold
    )
    
    website.current_qualification_status = new_qual_status
    
    try:
        db.commit()
        db.refresh(metric)
        db.refresh(website)
        return metric
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to add manual traffic for {website_id}: {e}")
        raise
