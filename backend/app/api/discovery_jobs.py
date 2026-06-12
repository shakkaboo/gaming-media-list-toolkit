from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
import math

from app.database import get_db
from app.models.enums import DiscoveryJobStatus
from app.schemas.discovery_job import DiscoveryJobCreate, DiscoveryJobDetail, DiscoveryJobListResponse, DiscoveryJobSummary
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
