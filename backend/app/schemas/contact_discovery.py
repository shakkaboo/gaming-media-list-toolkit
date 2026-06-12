from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.search import NormalizedCandidate

class ContactDiscoveryRequest(BaseModel):
    candidates: List[NormalizedCandidate] = Field(min_length=1)
    allow_uncertain: bool = False
    maximum_candidates: Optional[int] = Field(None, gt=0)
    maximum_pages_per_site: Optional[int] = Field(None, gt=0)
    include_named_contacts: bool = False
    include_generic_contacts: bool = True

class ContactPageCandidate(BaseModel):
    url: str
    page_type: str
    score: int
    reason_codes: List[str] = Field(default_factory=list)
    anchor_text: Optional[str] = None
    discovery_order: int

class ContactEvidence(BaseModel):
    source_url: str
    extraction_method: str
    source_page_type: str
    nearby_text: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    first_seen_order: int

class ExtractedContact(BaseModel):
    email: str
    normalized_email: str
    primary_type: str
    secondary_types: List[str] = Field(default_factory=list)
    is_role_based: bool
    is_named_contact: bool
    is_placeholder_suspected: bool
    confidence: float
    rank_score: int
    evidence: List[ContactEvidence] = Field(default_factory=list)

class ContactForm(BaseModel):
    page_url: str
    action_url: Optional[str] = None
    is_external: bool
    method: str
    purpose: str
    confidence: float
    field_names: List[str] = Field(default_factory=list)

class ContactDiscoveryResult(BaseModel):
    candidate_url: str
    registered_domain: str
    verification_status: str
    pages_considered: int
    pages_fetched: int
    page_errors: List[str] = Field(default_factory=list)
    robots_status: str
    contacts: List[ExtractedContact] = Field(default_factory=list)
    forms: List[ContactForm] = Field(default_factory=list)
    best_contact: Optional[ExtractedContact] = None
    success: bool
    error_code: Optional[str] = None
    safe_error: Optional[str] = None

class ContactDiscoveryPreviewResponse(BaseModel):
    results: List[ContactDiscoveryResult] = Field(default_factory=list)
    sites_processed: int = 0
    sites_with_contacts: int = 0
    contacts_found: int = 0
    forms_found: int = 0
    skipped_count: int = 0
    failed_count: int = 0
