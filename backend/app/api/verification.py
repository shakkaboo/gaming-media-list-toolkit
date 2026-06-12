from fastapi import APIRouter, Depends
from app.schemas.verification import VerificationRequest, VerificationPreviewResponse
from app.services.verification_service import VerificationService

router = APIRouter(prefix="/verification", tags=["Verification"])

def get_verification_service() -> VerificationService:
    return VerificationService()

@router.post("/preview", response_model=VerificationPreviewResponse)
async def preview_verification(
    request: VerificationRequest,
    service: VerificationService = Depends(get_verification_service)
):
    """
    Safely fetches candidate URLs and performs offline rule-based verification
    to determine if they represent genuine gaming media publications.
    Raw HTML is kept strictly internal and is never returned.
    """
    return await service.verify_candidates(request)
