import enum

class DiscoveryJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    completed_with_errors = "completed_with_errors"
    failed = "failed"
    cancelled = "cancelled"

class VerificationStatus(str, enum.Enum):
    verified = "verified"
    rejected = "rejected"
    uncertain = "uncertain"
    fetch_failed = "fetch_failed"

class QualificationStatus(str, enum.Enum):
    qualified = "qualified"
    upcoming = "upcoming"
    traffic_missing = "traffic_missing"
    rejected = "rejected"
    needs_review = "needs_review"

class ManualReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    needs_review = "needs_review"

class ContactType(str, enum.Enum):
    advertising = "advertising"
    partnerships = "partnerships"
    business = "business"
    sales = "sales"
    editorial = "editorial"
    editor = "editor"
    press = "press"
    general = "general"
    support = "support"
    privacy = "privacy"
    unknown = "unknown"

class ProcessingStage(str, enum.Enum):
    query_generation = "query_generation"
    search = "search"
    normalization = "normalization"
    deduplication = "deduplication"
    filtering = "filtering"
    fetching = "fetching"
    verification = "verification"
    traffic = "traffic"
    contact_discovery = "contact_discovery"
    contact_extraction = "contact_extraction"
    persistence = "persistence"
    unknown = "unknown"
