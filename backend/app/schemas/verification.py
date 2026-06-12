from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.search import NormalizedCandidate

class VerificationReason(BaseModel):
    code: str
    message: str
    weight: int
    evidence: List[str] = Field(default_factory=list)

class ExtractedSiteSignals(BaseModel):
    page_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_site_name: Optional[str] = None
    html_language: Optional[str] = None
    canonical_url: Optional[str] = None
    headings: List[str] = Field(default_factory=list)
    navigation_labels: List[str] = Field(default_factory=list)
    footer_text: List[str] = Field(default_factory=list)
    article_links: List[str] = Field(default_factory=list)
    author_links: List[str] = Field(default_factory=list)
    json_ld_types: List[str] = Field(default_factory=list)
    detected_publication_dates: List[str] = Field(default_factory=list)
    detected_categories: List[str] = Field(default_factory=list)
    challenge_indicators: List[str] = Field(default_factory=list)
    parking_indicators: List[str] = Field(default_factory=list)

class VerificationResult(BaseModel):
    requested_url: str
    final_url: str
    registered_domain: str
    score: int
    verification_status: str
    confidence: float
    
    gaming_relevance_score: int
    editorial_structure_score: int
    activity_score: int
    publication_identity_score: int
    negative_penalty: int
    
    positive_reasons: List[VerificationReason] = Field(default_factory=list)
    negative_reasons: List[VerificationReason] = Field(default_factory=list)
    detected_categories: List[str] = Field(default_factory=list)
    
    activity_status: str
    newest_detected_publication_date: Optional[str] = None
    article_count_estimate: int
    
    classifier_version: str
    analysed_at: datetime
    
    fetch_success: bool
    fetch_error_code: Optional[str] = None
    safe_error: Optional[str] = None
    
    expected_market: Optional[str] = None
    expected_language: Optional[str] = None
    detected_language: Optional[str] = None
    market_evidence: List[str] = Field(default_factory=list)

class VerificationPreviewResponse(BaseModel):
    results: List[VerificationResult] = Field(default_factory=list)
    verified_count: int = 0
    uncertain_count: int = 0
    rejected_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0

class VerificationRequest(BaseModel):
    candidates: List[NormalizedCandidate] = Field(min_length=1)
    expected_market: Optional[str] = Field(None, max_length=100)
    expected_language: Optional[str] = Field(None, max_length=50)
    verified_threshold: Optional[int] = Field(None, ge=0, le=100)
    uncertain_threshold: Optional[int] = Field(None, ge=0, le=100)
    maximum_candidates: Optional[int] = Field(None, gt=0)
    include_evidence: bool = True
