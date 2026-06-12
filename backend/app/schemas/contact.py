from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from app.models.enums import ContactType

class ContactResponse(BaseModel):
    id: UUID
    email: Optional[str] = None
    contact_type: ContactType
    source_url: str
    confidence: Optional[Decimal] = None
    is_primary: bool
    is_active: bool
    contact_form_url: Optional[str] = None
    social_platform: Optional[str] = None
    social_url: Optional[str] = None
    discovered_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
