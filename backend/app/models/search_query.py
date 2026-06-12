import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin

class SearchQuery(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "search_queries"

    discovery_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discovery_jobs.id", ondelete="CASCADE"), nullable=False)
    
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    market: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requested_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    discovery_job: Mapped["DiscoveryJob"] = relationship("DiscoveryJob", back_populates="search_queries")
    discovery_sources: Mapped[List["DiscoverySource"]] = relationship("DiscoverySource", back_populates="search_query")
    
    __table_args__ = (
        CheckConstraint("result_count >= 0", name="chk_sq_rc"),
        CheckConstraint("requested_limit > 0", name="chk_sq_rl"),
        CheckConstraint("attempt_count >= 0", name="chk_sq_ac"),
        UniqueConstraint("discovery_job_id", "query_text", name="uq_sq_job_query"),
        Index("ix_sq_job_id", "discovery_job_id"),
        Index("ix_sq_status", "status"),
    )
