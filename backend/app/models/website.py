from typing import List, Optional, Any
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON, Enum, Boolean, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.enums import VerificationStatus, QualificationStatus, ManualReviewStatus

class Website(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "websites"

    domain: Mapped[str] = mapped_column(String, index=True, nullable=False)
    canonical_key: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    is_multitenant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    homepage_url: Mapped[str] = mapped_column(Text, nullable=False)
    
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    language: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    categories: Mapped[Optional[List[Any]]] = mapped_column(JSON, nullable=True)
    
    current_verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verificationstatus", native_enum=True),
        default=VerificationStatus.uncertain,
        nullable=False,
        index=True
    )
    
    current_qualification_status: Mapped[QualificationStatus] = mapped_column(
        Enum(QualificationStatus, name="qualificationstatus", native_enum=True),
        default=QualificationStatus.needs_review,
        nullable=False,
        index=True
    )
    
    manual_review_status: Mapped[ManualReviewStatus] = mapped_column(
        Enum(ManualReviewStatus, name="manualreviewstatus", native_enum=True),
        default=ManualReviewStatus.pending,
        nullable=False,
        index=True
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    
    discovery_sources: Mapped[List["DiscoverySource"]] = relationship("DiscoverySource", back_populates="website")
    verifications: Mapped[List["WebsiteVerification"]] = relationship("WebsiteVerification", back_populates="website")
    traffic_metrics: Mapped[List["TrafficMetric"]] = relationship("TrafficMetric", back_populates="website")
    contacts: Mapped[List["Contact"]] = relationship("Contact", back_populates="website")
    processing_errors: Mapped[List["ProcessingError"]] = relationship("ProcessingError", back_populates="website")
    
    __table_args__ = (
        CheckConstraint("length(domain) > 0", name="chk_web_domain"),
        CheckConstraint("length(homepage_url) > 0", name="chk_web_homepage"),
    )
