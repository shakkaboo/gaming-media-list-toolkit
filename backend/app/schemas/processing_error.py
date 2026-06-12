from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from app.models.enums import ProcessingStage

class ProcessingErrorResponse(BaseModel):
    id: UUID
    stage: ProcessingStage
    error_type: str
    message: str
    url: Optional[str] = None
    is_retryable: bool
    attempt_number: int
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
