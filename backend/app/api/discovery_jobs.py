from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
import math

from app.database import get_db
from app.models.enums import DiscoveryJobStatus
from app.schemas.discovery_job import DiscoveryJobCreate, DiscoveryJobDetail, DiscoveryJobListResponse, DiscoveryJobSummary
from app.schemas.discovery_orchestration import DiscoveryRunSummary
from app.schemas.discovery_results import DiscoveryResultsResponse
from app.schemas.common import PaginationMeta
from app.services.discovery_job_service import create_job, get_job, list_jobs

router = APIRouter(prefix="/discovery/jobs", tags=["Discovery Jobs"])

@router.post("", response_model=DiscoveryJobDetail, status_code=status.HTTP_201_CREATED)
def api_create_job(payload: DiscoveryJobCreate, db: Session = Depends(get_db)):
    job = create_job(db, payload)
    return DiscoveryJobDetail.model_validate(job)

@router.get("", response_model=DiscoveryJobListResponse)
def api_list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    job_status: Optional[DiscoveryJobStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    items, total = list_jobs(db, page, page_size, job_status)

    total_pages = math.ceil(total / page_size) if total > 0 else 0
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1
    )

    return DiscoveryJobListResponse(
        items=[DiscoveryJobSummary.model_validate(i) for i in items],
        pagination=pagination
    )

@router.get("/{job_id}", response_model=DiscoveryJobDetail)
def api_get_job(job_id: UUID, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    return DiscoveryJobDetail.model_validate(job)

@router.post("/{job_id}/run", response_model=DiscoveryRunSummary)
async def api_run_job(job_id: UUID):
    from app.services.discovery_orchestrator import DiscoveryOrchestrator
    from app.database import SessionLocal
    from app.config import get_settings
    from app.services.fetch_service import FetchService
    from app.services.verification_service import VerificationService
    from fastapi import HTTPException
    from app.exceptions import ResourceNotFoundError, InvalidOperationError
    from app.services.discovery_persistence import InvalidJobTransition, JobNotFound, IncompleteJobFinalization, PersistenceConflict, PersistenceFailure
    import logging
    logger = logging.getLogger(__name__)

    from app.services.discovery_job_service import get_job
    try:
        with SessionLocal() as db:
            get_job(db, job_id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail=f"DiscoveryJob {job_id} not found")

    orchestrator = DiscoveryOrchestrator(
        session_factory=SessionLocal,
        settings=get_settings(),
        fetch_service=FetchService(),
        verification_service=VerificationService()
    )

    try:
        summary = await orchestrator.run_job(job_id)
        return summary
    except JobNotFound:
        raise HTTPException(status_code=404, detail=f"DiscoveryJob {job_id} not found")
    except InvalidJobTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    except IncompleteJobFinalization as e:
        raise HTTPException(status_code=409, detail=str(e))
    except PersistenceConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except PersistenceFailure as e:
        logger.error(f"Persistence failure running job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="A database persistence error occurred")
    except Exception as e:
        logger.exception(f"Unexpected error running job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="An unexpected internal server error occurred")

@router.get("/{job_id}/results", response_model=DiscoveryResultsResponse)
def api_get_job_results(
    job_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verification_status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    from app.services.discovery_job_service import get_job_results, get_job
    from app.exceptions import ResourceNotFoundError
    from fastapi import HTTPException
    try:
        results, total = get_job_results(
            db=db,
            job_id=job_id,
            page=page,
            page_size=page_size,
            verification_status=verification_status
        )
        job = get_job(db, job_id)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return DiscoveryResultsResponse(
        job_id=job_id,
        job_status=getattr(job.status, "value", str(job.status)),
        page=page,
        page_size=page_size,
        total=total,
        items=results
    )
