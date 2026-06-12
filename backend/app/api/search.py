from fastapi import APIRouter
from app.schemas.search import (
    QueryGenerationRequest,
    QueryGenerationResponse,
    SearchPreviewRequest,
    SearchPreviewResponse,
    CandidatePreviewRequest,
    CandidatePreviewResponse
)
from app.services.search_service import preview_queries, preview_search, preview_candidates

router = APIRouter(prefix="/search", tags=["Search"])

@router.post("/queries/preview", response_model=QueryGenerationResponse)
def generate_queries_preview(request: QueryGenerationRequest):
    return preview_queries(request)

@router.post("/results/preview", response_model=SearchPreviewResponse)
async def fetch_results_preview(request: SearchPreviewRequest):
    return await preview_search(request)

@router.post("/candidates/preview", response_model=CandidatePreviewResponse)
async def fetch_candidates_preview(request: CandidatePreviewRequest):
    return await preview_candidates(request)
