import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, get_utc_now

class DiscoverySource(Base, UUIDMixin):
    __tablename__ = "discovery_sources"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)
    discovery_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discovery_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    search_query_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("search_queries.id", ondelete="SET NULL"), nullable=True, index=True)
    
    provider: Mapped[str] = mapped_column(String, nullable=False, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    result_url: Mapped[str] = mapped_column(Text, nullable=False)
    
    result_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    website: Mapped["Website"] = relationship("Website", back_populates="discovery_sources")
    discovery_job: Mapped["DiscoveryJob"] = relationship("DiscoveryJob", back_populates="discovery_sources")
    search_query: Mapped[Optional["SearchQuery"]] = relationship("SearchQuery", back_populates="discovery_sources")

    __table_args__ = (
        CheckConstraint("result_position > 0", name="chk_ds_pos"),
        UniqueConstraint("website_id", "discovery_job_id", "query_text", "result_url", name="uq_ds_website_job_query_url"),
    )
