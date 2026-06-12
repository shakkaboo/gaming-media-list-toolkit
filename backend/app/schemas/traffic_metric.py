from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal
import math

class ManualTrafficCreate(BaseModel):
    monthly_visits: Decimal = Field(..., ge=0)
    pages_per_visit: Decimal = Field(..., ge=0)
    growth_rate: Optional[Decimal] = None
    measurement_month: Optional[date] = None
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator('monthly_visits', 'pages_per_visit', 'growth_rate', 'confidence')
    def check_nan_inf(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None:
            if v.is_nan() or v.is_infinite():
                raise ValueError("NaN or infinite values are not allowed")
        return v

class TrafficMetricResponse(BaseModel):
    id: UUID
    website_id: UUID
    discovery_job_id: Optional[UUID] = None
    provider: str
    monthly_visits: Optional[Decimal] = None
    pages_per_visit: Optional[Decimal] = None
    estimated_pageviews: Optional[Decimal] = None
    growth_rate: Optional[Decimal] = None
    measurement_month: Optional[date] = None
    confidence: Optional[Decimal] = None
    is_manual: bool
    retrieved_at: datetime
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
