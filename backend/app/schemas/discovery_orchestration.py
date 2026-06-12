from uuid import UUID
from pydantic import BaseModel

class DiscoveryRunSummary(BaseModel):
    job_id: UUID
    attempt_number: int
    final_status: str
    queries_total: int
    queries_executed: int
    queries_skipped: int
    websites_discovered: int
    websites_processed: int
    websites_verified: int
    websites_uncertain: int
    websites_rejected: int
    errors_count: int
