from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, Literal
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal
import math

class ManualTrafficCreate(BaseModel):
    metric_type: Literal['monthly_pageviews', 'monthly_visits', 'estimated_monthly_pageviews']
    monthly_visits: Optional[Decimal] = Field(None, ge=0)
    pages_per_visit: Optional[Decimal] = Field(None, ge=0)
    monthly_pageviews: Optional[Decimal] = Field(None, ge=0)

    growth_rate: Optional[Decimal] = None
    measurement_month: Optional[date] = None
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)

    evidence_url: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator('monthly_visits', 'pages_per_visit', 'monthly_pageviews', 'growth_rate', 'confidence')
    def check_nan_inf(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None:
            if v.is_nan() or v.is_infinite():
                raise ValueError("NaN or infinite values are not allowed")
        return v

    @model_validator(mode='after')
    def validate_metric_type_requirements(self) -> 'ManualTrafficCreate':
        if self.metric_type == 'monthly_pageviews':
            if self.monthly_pageviews is None:
                raise ValueError("monthly_pageviews is required when metric_type is monthly_pageviews")
        elif self.metric_type == 'monthly_visits':
            if self.monthly_visits is None:
                raise ValueError("monthly_visits is required when metric_type is monthly_visits")
        elif self.metric_type == 'estimated_monthly_pageviews':
            if self.monthly_visits is None or self.pages_per_visit is None:
                raise ValueError("monthly_visits and pages_per_visit are required when metric_type is estimated_monthly_pageviews")
        return self

class TrafficMetricResponse(BaseModel):
    id: UUID
    website_id: UUID
    discovery_job_id: Optional[UUID] = None
    provider: str
    metric_type: str
    monthly_visits: Optional[Decimal] = None
    pages_per_visit: Optional[Decimal] = None
    monthly_pageviews: Optional[Decimal] = None
    estimated_pageviews: Optional[Decimal] = None
    growth_rate: Optional[Decimal] = None
    measurement_month: Optional[date] = None
    confidence: Optional[Decimal] = None
    is_manual: bool
    retrieved_at: datetime
    evidence_url: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
