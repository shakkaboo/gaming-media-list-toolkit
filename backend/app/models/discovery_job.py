from typing import List, Optional, Any
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, Text, DateTime, JSON, Enum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.enums import DiscoveryJobStatus

class DiscoveryJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "discovery_jobs"

    status: Mapped[DiscoveryJobStatus] = mapped_column(
        Enum(DiscoveryJobStatus, name="discoveryjobstatus", native_enum=True),
        default=DiscoveryJobStatus.pending,
        nullable=False
    )

    target_market: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    categories: Mapped[List[Any]] = mapped_column(JSON, nullable=False)

    minimum_pageviews: Mapped[int] = mapped_column(BigInteger, nullable=False)
    maximum_queries: Mapped[int] = mapped_column(Integer, nullable=False)
    results_per_query: Mapped[int] = mapped_column(Integer, nullable=False)

    search_provider: Mapped[str] = mapped_column(String, nullable=False)
    traffic_provider: Mapped[str] = mapped_column(String, nullable=False)

    # Counters
    queries_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queries_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candidates_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates_removed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candidates_filtered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sites_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sites_verified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sites_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sites_qualified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sites_upcoming: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sites_traffic_missing: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    attempt_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    websites_uncertain: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    contacts_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optional
    failure_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    search_queries: Mapped[List["SearchQuery"]] = relationship("SearchQuery", back_populates="discovery_job", cascade="all, delete-orphan")
    discovery_sources: Mapped[List["DiscoverySource"]] = relationship("DiscoverySource", back_populates="discovery_job", cascade="all, delete-orphan")
    processing_errors: Mapped[List["ProcessingError"]] = relationship("ProcessingError", back_populates="discovery_job")

    __table_args__ = (
        CheckConstraint("minimum_pageviews >= 0", name="chk_dj_min_pv"),
        CheckConstraint("maximum_queries > 0", name="chk_dj_max_queries"),
        CheckConstraint("results_per_query > 0", name="chk_dj_res_per_query"),
        CheckConstraint("queries_generated >= 0", name="chk_dj_qg"),
        CheckConstraint("queries_completed >= 0", name="chk_dj_qc"),
        CheckConstraint("candidates_found >= 0", name="chk_dj_cf"),
        CheckConstraint("duplicates_removed >= 0", name="chk_dj_dr"),
        CheckConstraint("candidates_filtered >= 0", name="chk_dj_cf_filt"),
        CheckConstraint("sites_fetched >= 0", name="chk_dj_sf"),
        CheckConstraint("sites_verified >= 0", name="chk_dj_sv"),
        CheckConstraint("sites_rejected >= 0", name="chk_dj_sr"),
        CheckConstraint("sites_qualified >= 0", name="chk_dj_sq"),
        CheckConstraint("sites_upcoming >= 0", name="chk_dj_su"),
        CheckConstraint("sites_traffic_missing >= 0", name="chk_dj_stm"),
        CheckConstraint("errors_count >= 0", name="chk_dj_ec"),
    )
