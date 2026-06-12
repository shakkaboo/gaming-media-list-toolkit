from sqlalchemy.orm import Session
from uuid import UUID
from typing import Tuple, List, Optional
import logging

from app.models.enums import DiscoveryJobStatus
from app.models.discovery_job import DiscoveryJob
from app.schemas.discovery_job import DiscoveryJobCreate
from app.exceptions import ResourceNotFoundError
from app.config import get_settings

logger = logging.getLogger(__name__)

def create_job(db: Session, payload: DiscoveryJobCreate) -> DiscoveryJob:
    settings = get_settings()
    
    job = DiscoveryJob(
        status=DiscoveryJobStatus.pending,
        target_market=payload.target_market,
        language=payload.language,
        categories=payload.categories,
        minimum_pageviews=payload.minimum_pageviews,
        maximum_queries=payload.maximum_queries,
        results_per_query=payload.results_per_query,
        search_provider=settings.SEARCH_PROVIDER,
        traffic_provider=settings.TRAFFIC_PROVIDER,
        queries_generated=0,
        queries_completed=0,
        candidates_found=0,
        duplicates_removed=0,
        candidates_filtered=0,
        sites_fetched=0,
        sites_verified=0,
        sites_rejected=0,
        sites_qualified=0,
        sites_upcoming=0,
        sites_traffic_missing=0,
        errors_count=0
    )
    
    db.add(job)
    try:
        db.commit()
        db.refresh(job)
        return job
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create discovery job: {e}")
        raise

def get_job(db: Session, job_id: UUID) -> DiscoveryJob:
    job = db.query(DiscoveryJob).filter(DiscoveryJob.id == job_id).first()
    if not job:
        raise ResourceNotFoundError(f"DiscoveryJob {job_id} not found")
    return job

def list_jobs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status: Optional[DiscoveryJobStatus] = None
) -> Tuple[List[DiscoveryJob], int]:
    query = db.query(DiscoveryJob)
    
    if status is not None:
        query = query.filter(DiscoveryJob.status == status)
        
    total = query.count()
    
    offset = (page - 1) * page_size
    items = query.order_by(DiscoveryJob.created_at.desc()).offset(offset).limit(page_size).all()
    
    return items, total
