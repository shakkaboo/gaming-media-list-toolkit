from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID

class DiscoverySourceResponse(BaseModel):
    id: UUID
    provider: str
    query_text: str
    result_url: str
    result_title: Optional[str] = None
    result_snippet: Optional[str] = None
    result_position: Optional[int] = None
    discovered_at: datetime

    model_config = ConfigDict(from_attributes=True)
