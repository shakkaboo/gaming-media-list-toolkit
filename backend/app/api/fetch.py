from fastapi import APIRouter
from app.schemas.fetch import FetchRequest, FetchPreviewResponse
from app.services.fetch_service import FetchService

router = APIRouter(prefix="/fetch", tags=["Fetch"])

@router.post("/preview", response_model=FetchPreviewResponse)
async def fetch_preview_api(request: FetchRequest):
    service = FetchService()
    return await service.fetch_preview(request)
