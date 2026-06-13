from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from uuid import UUID
import logging
from typing import Optional

from app.models.enums import VerificationStatus, QualificationStatus
from app.models.website import Website
from app.models.traffic_metric import TrafficMetric
from app.models.discovery_job import DiscoveryJob
from app.models.enums import QualificationStatus, ProcessingStage
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

    if estimated_pageviews >= minimum_pageviews:
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

async def check_website_traffic(
    db: Session,
    website_id: UUID,
    job_id: Optional[UUID],
    provider_name: str,
    minimum_pageviews: Decimal
) -> Optional[TrafficMetric]:
    from app.providers.traffic.factory import get_traffic_provider
    from app.services.discovery_persistence import DiscoveryPersistenceService
    from app.models.enums import ProcessingStage

    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        return None

    # Only verified websites are eligible for traffic lookup
    if website.current_verification_status != VerificationStatus.verified:
        new_qual_status = determine_qualification_status(
            estimated_pageviews=None,
            verification_status=website.current_verification_status,
            minimum_pageviews=minimum_pageviews
        )
        website.current_qualification_status = new_qual_status
        db.commit()
        return None

    provider = get_traffic_provider(provider_name, get_settings())

    try:
        estimate = await provider.get_traffic(website.domain)
    except Exception as e:
        if job_id:
            job = db.query(DiscoveryJob).filter(DiscoveryJob.id == job_id).first()
            attempt_num = job.attempt_number if job else 1
            persistence = DiscoveryPersistenceService(db)
            persistence.record_processing_error(
                job_id=job_id,
                attempt_number=attempt_num,
                stage=ProcessingStage.traffic,
                error_code="traffic_crash",
                safe_message=str(e)[:200],
                retryable=True,
                website_id=website_id
            )
            db.commit()
        website.current_qualification_status = QualificationStatus.needs_review
        db.commit()
        return None

    if not estimate.has_data:
        if estimate.error_code and job_id:
            job = db.query(DiscoveryJob).filter(DiscoveryJob.id == job_id).first()
            attempt_num = job.attempt_number if job else 1
            persistence = DiscoveryPersistenceService(db)
            persistence.record_processing_error(
                job_id=job_id,
                attempt_number=attempt_num,
                stage=ProcessingStage.traffic,
                error_code=estimate.error_code,
                safe_message=estimate.safe_error or "Traffic fetch failed",
                retryable=False,
                website_id=website_id
            )
            db.commit()

        website.current_qualification_status = QualificationStatus.traffic_missing
        db.commit()
        return None

    try:
        estimated_pageviews = calculate_estimated_pageviews(
            estimate.monthly_visits or Decimal("0"),
            estimate.pages_per_visit or Decimal("0")
        )
    except ValueError:
        estimated_pageviews = None

    metric = TrafficMetric(
        website_id=website.id,
        discovery_job_id=job_id,
        provider=estimate.provider,
        monthly_visits=estimate.monthly_visits,
        pages_per_visit=estimate.pages_per_visit,
        estimated_pageviews=estimated_pageviews,
        growth_rate=estimate.growth_rate,
        measurement_month=estimate.measurement_month,
        confidence=estimate.confidence,
        is_manual=False,
        notes=estimate.notes
    )

    db.add(metric)

    new_qual_status = determine_qualification_status(
        estimated_pageviews=estimated_pageviews,
        verification_status=website.current_verification_status,
        minimum_pageviews=minimum_pageviews
    )
    website.current_qualification_status = new_qual_status

    try:
        db.commit()
        db.refresh(metric)
        return metric
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to persist traffic for {website_id}: {e}")
        return None
