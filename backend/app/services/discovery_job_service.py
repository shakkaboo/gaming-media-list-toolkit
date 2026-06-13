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
    return items, total

def get_job_results(
    db: Session,
    job_id: UUID,
    page: int = 1,
    page_size: int = 20,
    verification_status: Optional[str] = None
) -> Tuple[List[dict], int]:
    from sqlalchemy import select, func, distinct
    from app.models.website import Website
    from app.models.discovery_source import DiscoverySource
    from app.models.website_verification import WebsiteVerification
    from app.models.search_query import SearchQuery

    # Verify job exists
    get_job(db, job_id)

    # Latest verification subquery
    subq_verif = (
        select(
            WebsiteVerification.website_id,
            WebsiteVerification.status,
            WebsiteVerification.score,
            WebsiteVerification.confidence,
            WebsiteVerification.classifier_version,
            WebsiteVerification.verified_at,
            func.row_number().over(
                partition_by=WebsiteVerification.website_id,
                order_by=(
                    WebsiteVerification.attempt_number.desc(),
                    WebsiteVerification.verified_at.desc(),
                    WebsiteVerification.id.desc()
                )
            ).label("rn")
        )
        .where(WebsiteVerification.discovery_job_id == job_id)
        .subquery()
    )

    latest_verif = (
        select(subq_verif)
        .where(subq_verif.c.rn == 1)
        .subquery()
    )

    # Base query for websites in this job
    base_website_query = select(Website).where(
        Website.id.in_(
            select(DiscoverySource.website_id)
            .where(DiscoverySource.discovery_job_id == job_id)
        )
    )

    if verification_status:
        # User requested a specific status, so inner join and filter
        base_website_query = (
            base_website_query
            .join(latest_verif, Website.id == latest_verif.c.website_id)
            .where(latest_verif.c.status == verification_status)
        )

    # Get total
    total = db.execute(select(func.count()).select_from(base_website_query.subquery())).scalar() or 0

    # Paginate websites
    offset = (page - 1) * page_size
    websites = db.execute(
        base_website_query.order_by(Website.id).offset(offset).limit(page_size)
    ).scalars().all()

    website_ids = [w.id for w in websites]

    if not website_ids:
        return [], 0

    # Fetch DiscoverySources and SearchQueries for these websites
    sources_stmt = (
        select(DiscoverySource, SearchQuery.query_text)
        .join(SearchQuery, DiscoverySource.search_query_id == SearchQuery.id)
        .where(DiscoverySource.discovery_job_id == job_id, DiscoverySource.website_id.in_(website_ids))
    )
    sources_rows = db.execute(sources_stmt).all()

    from collections import defaultdict
    sources_by_website = defaultdict(list)
    queries_by_website = defaultdict(set)
    for ds, qtext in sources_rows:
        sources_by_website[ds.website_id].append(ds)
        queries_by_website[ds.website_id].add(qtext)

    # Fetch latest verifications for these websites
    verifs_stmt = select(latest_verif).where(latest_verif.c.website_id.in_(website_ids))
    verifs_rows = db.execute(verifs_stmt).all()
    verifs_by_website = {r.website_id: r for r in verifs_rows}

    results = []
    for w in websites:
        v = verifs_by_website.get(w.id)
        q_set = queries_by_website.get(w.id, set())

        v_status = getattr(v.status, "value", str(v.status)) if v and v.status else None
        # Handle enum casting specifically if requested verification_status filter is applied
        if verification_status and v_status != getattr(verification_status, "value", str(verification_status)):
            continue

        results.append({
            "website_id": w.id,
            "name": w.name,
            "domain": w.domain,
            "homepage_url": w.homepage_url,
            "canonical_key": w.canonical_key,
            "is_multitenant": getattr(w, "is_multitenant", False),
            "verification_status": v_status,
            "verification_score": float(v.score) if v and v.score is not None else None,
            "confidence": float(v.confidence) if v and v.confidence is not None else None,
            "activity_status": "active" if getattr(w, "is_active", True) else "inactive",
            "detected_categories": w.categories or [],
            "classifier_version": v.classifier_version if v else None,
            "source_count": len(sources_by_website.get(w.id, [])),
            "source_queries": sorted(list(q_set)),
            "latest_verified_at": v.verified_at if v else None
        })

    return results, total
