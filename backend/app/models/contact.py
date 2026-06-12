import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import text, String, Text, DateTime, Boolean, Enum, Numeric, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, get_utc_now
from app.models.enums import ContactType

class Contact(Base, UUIDMixin):
    __tablename__ = "contacts"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)
    discovery_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("discovery_jobs.id", ondelete="SET NULL"), nullable=True)
    
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    contact_type: Mapped[ContactType] = mapped_column(
        Enum(ContactType, name="contacttype", native_enum=True),
        default=ContactType.unknown,
        nullable=False,
        index=True
    )
    
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    
    contact_form_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    social_platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    social_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    website: Mapped["Website"] = relationship("Website", back_populates="contacts")

    __table_args__ = (
        CheckConstraint("length(source_url) > 0", name="chk_cnt_src_url"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="chk_cnt_conf"),
        CheckConstraint(
            "email IS NOT NULL OR contact_form_url IS NOT NULL OR social_url IS NOT NULL",
            name="chk_cnt_method_exists"
        ),
        Index(
            "ix_contacts_unique_email",
            "website_id", text("lower(email)"),
            unique=True,
            postgresql_where=text("email IS NOT NULL")
        ),
        Index(
            "ix_contacts_unique_form",
            "website_id", "contact_form_url",
            unique=True,
            postgresql_where=text("contact_form_url IS NOT NULL")
        )
    )
