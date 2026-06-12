# Import all models to ensure they are registered with Base.metadata

from app.database import Base

from app.models.enums import (
    DiscoveryJobStatus,
    VerificationStatus,
    QualificationStatus,
    ManualReviewStatus,
    ContactType,
    ProcessingStage,
)

from app.models.base import UUIDMixin, TimestampMixin

from app.models.website import Website
from app.models.discovery_job import DiscoveryJob
from app.models.search_query import SearchQuery
from app.models.discovery_source import DiscoverySource
from app.models.website_verification import WebsiteVerification
from app.models.traffic_metric import TrafficMetric
from app.models.contact import Contact
from app.models.processing_error import ProcessingError

__all__ = [
    "Base",
    "DiscoveryJobStatus",
    "VerificationStatus",
    "QualificationStatus",
    "ManualReviewStatus",
    "ContactType",
    "ProcessingStage",
    "UUIDMixin",
    "TimestampMixin",
    "Website",
    "DiscoveryJob",
    "SearchQuery",
    "DiscoverySource",
    "WebsiteVerification",
    "TrafficMetric",
    "Contact",
    "ProcessingError",
]
