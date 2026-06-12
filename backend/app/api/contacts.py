from fastapi import APIRouter, Depends
from typing import Optional

from app.schemas.contact_discovery import ContactDiscoveryRequest, ContactDiscoveryPreviewResponse
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["Contacts"])

def get_contact_service() -> ContactService:
    return ContactService()

@router.post("/preview", response_model=ContactDiscoveryPreviewResponse)
async def preview_contacts(
    request: ContactDiscoveryRequest,
    service: ContactService = Depends(get_contact_service)
):
    """
    Safely fetch and extract contacts from the given candidates.
    Does not write to the database. Does not return raw HTML.
    Internally verifies before proceeding.
    """
    return await service.discover_contacts_batch(request)
