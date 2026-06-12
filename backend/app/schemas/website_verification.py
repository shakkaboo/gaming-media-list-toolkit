from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from app.models.enums import VerificationStatus

class WebsiteVerificationResponse(BaseModel):
    id: UUID
    score: int
    status: VerificationStatus
    confidence: Optional[Decimal] = None
    positive_reasons: List[Any]
    negative_reasons: List[Any]
    detected_categories: Optional[List[Any]] = None
    activity_status: Optional[str] = None
    classifier_version: str
    homepage_title: Optional[str] = None
    homepage_description: Optional[str] = None
    verified_at: datetime

    model_config = ConfigDict(from_attributes=True)
