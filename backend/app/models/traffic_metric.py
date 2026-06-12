import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Text, DateTime, Date, Numeric, Boolean, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, get_utc_now

class TrafficMetric(Base, UUIDMixin):
    __tablename__ = "traffic_metrics"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)
    discovery_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("discovery_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    
    provider: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    monthly_visits: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    pages_per_visit: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    estimated_pageviews: Mapped[Optional[float]] = mapped_column(Numeric(24, 2), nullable=True)
    growth_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    
    measurement_month: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False, index=True)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    website: Mapped["Website"] = relationship("Website", back_populates="traffic_metrics")

    __table_args__ = (
        CheckConstraint("length(provider) > 0", name="chk_tm_provider"),
        CheckConstraint("monthly_visits >= 0", name="chk_tm_mv"),
        CheckConstraint("pages_per_visit >= 0", name="chk_tm_ppv"),
        CheckConstraint("estimated_pageviews >= 0", name="chk_tm_epv"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="chk_tm_conf"),
    )
