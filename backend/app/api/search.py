from fastapi import APIRouter
from app.schemas.search import (
    QueryGenerationRequest,
    QueryGenerationResponse,
    SearchPreviewRequest,
    SearchPreviewResponse
)
from app.services.search_service import preview_queries, preview_search

router = APIRouter(prefix="/search", tags=["Search"])

@router.post("/queries/preview", response_model=QueryGenerationResponse)
def generate_queries_preview(request: QueryGenerationRequest):
    return preview_queries(request)

@router.post("/results/preview", response_model=SearchPreviewResponse)
async def fetch_results_preview(request: SearchPreviewRequest):
    return await preview_search(request)
