from typing import Optional
from decimal import Decimal
from pydantic import BaseModel
from datetime import date

class TrafficEstimate(BaseModel):
    provider: str
    has_data: bool
    monthly_visits: Optional[Decimal] = None
    pages_per_visit: Optional[Decimal] = None
    growth_rate: Optional[Decimal] = None
    measurement_month: Optional[date] = None
    confidence: Optional[Decimal] = None
    notes: Optional[str] = None
    error_code: Optional[str] = None
    safe_error: Optional[str] = None
