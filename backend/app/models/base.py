import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column, declarative_mixin

from app.database import Base

def get_utc_now():
    return datetime.now(timezone.utc)

@declarative_mixin
class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

@declarative_mixin
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now
    )
