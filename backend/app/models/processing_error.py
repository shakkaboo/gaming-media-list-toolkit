import uuid
from datetime import datetime
from typing import Optional, Any, Dict
from sqlalchemy import String, Integer, Text, DateTime, JSON, Enum, Boolean, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, get_utc_now
from app.models.enums import ProcessingStage

class ProcessingError(Base, UUIDMixin):
    __tablename__ = "processing_errors"

    discovery_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("discovery_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    website_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("websites.id", ondelete="SET NULL"), nullable=True, index=True)
    search_query_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("search_queries.id", ondelete="SET NULL"), nullable=True, index=True)
    
    stage: Mapped[ProcessingStage] = mapped_column(
        Enum(ProcessingStage, name="processingstage", native_enum=True),
        default=ProcessingStage.unknown,
        nullable=False,
        index=True
    )
    error_type: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False, index=True)

    website: Mapped[Optional["Website"]] = relationship("Website", back_populates="processing_errors")
    discovery_job: Mapped[Optional["DiscoveryJob"]] = relationship("DiscoveryJob", back_populates="processing_errors")

    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="chk_pe_attempt"),
        CheckConstraint("length(error_type) > 0", name="chk_pe_type"),
        CheckConstraint("length(message) > 0", name="chk_pe_msg"),
    )
