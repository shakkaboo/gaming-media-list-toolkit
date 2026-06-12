import uuid
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import String, Integer, Text, DateTime, JSON, Enum, Numeric, ForeignKey, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, get_utc_now
from app.models.enums import VerificationStatus

class WebsiteVerification(Base, UUIDMixin):
    __tablename__ = "website_verifications"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)
    discovery_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("discovery_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verificationstatus", native_enum=True),
        nullable=False,
        index=True
    )
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    
    positive_reasons: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    negative_reasons: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    detected_categories: Mapped[Optional[List[Any]]] = mapped_column(JSON, nullable=True)
    
    activity_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    classifier_version: Mapped[str] = mapped_column(String, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False, server_default="1")
    
    homepage_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    homepage_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False, index=True)

    website: Mapped["Website"] = relationship("Website", back_populates="verifications")

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="chk_wv_score"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="chk_wv_conf"),
        CheckConstraint("length(classifier_version) > 0", name="chk_wv_ver"),
        UniqueConstraint("website_id", "discovery_job_id", "attempt_number", "classifier_version", name="uq_wv_job_site_attempt_version"),
    )
