from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.search import NormalizedCandidate

class AcquisitionEvidenceContext(BaseModel):
    transport_success: bool = False
    usable_evidence_found: bool = False
    usable_primary_html: bool = False
    usable_supporting_html_count: int = 0
    valid_feed_entry_count: int = 0
    structured_article_evidence_count: int = 0
    failure_category: Optional[str] = None
    challenge_detected: bool = False
    javascript_shell_detected: bool = False

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
    
    page_type: str = "primary"
    source_url: str = ""
    
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

class V2ShadowResult(BaseModel):
    """Shadow result from v2 classifier — for review only, does not affect production decision."""
    v2_predicted_status: str
    v2_relevance_label: str
    v2_market_status: str
    gaming_score: int
    media_score: int
    market_score: int
    activity_score: int
    technical_score: int
    component_sum: int
    contextual_deductions: int
    total_score: int
    hard_rejection_rule: Optional[str] = None
    hard_rejection_evidence: List[str] = Field(default_factory=list)
    decision_override: Optional[str] = None
    v2_explanation: str
    review_recommendation: str  # "agree" | "v2_abstained" | "review_v2_positive" | "review_v2_negative" | "review"


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
    
    predicted_status: Optional[str] = None
    relevance_label: Optional[str] = None
    market_status: Optional[str] = None
    v2_shadow: Optional[V2ShadowResult] = None

from typing import Union

class VerificationPreviewResponse(BaseModel):
    results: Union[List['VerificationResultV2'], List[VerificationResult]] = Field(default_factory=list)
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
    classifier_version: str = "baseline"
    
    gaming_minimum: Optional[int] = None
    media_minimum: Optional[int] = None
    market_minimum: Optional[int] = None
    technical_minimum: Optional[int] = None

class EvidenceItem(BaseModel):
    source: str
    matched_term: str
    page_type: str
    reason: str

class NormalizedMultilingualEvidence(BaseModel):
    gaming_identity_terms: List[EvidenceItem] = Field(default_factory=list)
    gaming_navigation_terms: List[EvidenceItem] = Field(default_factory=list)
    gaming_article_titles: List[EvidenceItem] = Field(default_factory=list)
    editorial_navigation_terms: List[EvidenceItem] = Field(default_factory=list)
    article_like_links: List[EvidenceItem] = Field(default_factory=list)
    publication_dates: List[EvidenceItem] = Field(default_factory=list)
    author_or_byline_evidence: List[EvidenceItem] = Field(default_factory=list)
    archive_or_category_evidence: List[EvidenceItem] = Field(default_factory=list)
    publication_identity_evidence: List[EvidenceItem] = Field(default_factory=list)
    market_language_evidence: List[EvidenceItem] = Field(default_factory=list)
    market_location_evidence: List[EvidenceItem] = Field(default_factory=list)
    market_editorial_focus: List[EvidenceItem] = Field(default_factory=list)
    recent_content_dates: List[EvidenceItem] = Field(default_factory=list)
    feed_activity_evidence: List[EvidenceItem] = Field(default_factory=list)
    store_identity_signals: List[EvidenceItem] = Field(default_factory=list)
    developer_identity_signals: List[EvidenceItem] = Field(default_factory=list)
    publisher_identity_signals: List[EvidenceItem] = Field(default_factory=list)
    hardware_identity_signals: List[EvidenceItem] = Field(default_factory=list)
    casino_identity_signals: List[EvidenceItem] = Field(default_factory=list)
    forum_identity_signals: List[EvidenceItem] = Field(default_factory=list)
    esports_identity_signals: List[EvidenceItem] = Field(default_factory=list)
    single_game_identity_signals: List[EvidenceItem] = Field(default_factory=list)
    technical_evidence: List[EvidenceItem] = Field(default_factory=list)

class VerificationResultV2(BaseModel):
    requested_url: str
    final_url: str
    registered_domain: str
    
    classifier_version: str
    
    gaming_score: int
    media_score: int
    market_score: int
    activity_score: int
    technical_score: int
    
    component_sum: int
    contextual_deductions: int
    total_score: int
    
    positive_signals: List[VerificationReason] = Field(default_factory=list)
    negative_signals: List[VerificationReason] = Field(default_factory=list)
    
    hard_rejection_rule: Optional[str] = None
    hard_rejection_evidence: List[str] = Field(default_factory=list)
    hard_rejection_confidence: float = 0.0
    
    predicted_status: str
    relevance_label: str
    market_status: str
    decision_reason: str
    decision_override: Optional[str] = None
    
    evidence: NormalizedMultilingualEvidence = Field(default_factory=NormalizedMultilingualEvidence)
    
    expected_market: Optional[str] = None
    expected_language: Optional[str] = None
    
    analysed_at: datetime
    fetch_success: bool
    fetch_error_code: Optional[str] = None
    safe_error: Optional[str] = None
