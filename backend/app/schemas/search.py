from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

class GeneratedSearchQuery(BaseModel):
    query_text: str = Field(..., max_length=500)
    category: str
    market: str
    language: str
    template_name: str
    page: int = Field(default=1, ge=1)

class SearchResult(BaseModel):
    url: str
    title: str
    snippet: Optional[str] = None
    query_text: str
    provider: str
    position: int
    published_at: Optional[datetime] = None
    language: Optional[str] = None

class SearchPreviewError(BaseModel):
    query_text: str
    error_type: str
    message: str

class QueryGenerationRequest(BaseModel):
    market: str = Field(..., min_length=1, max_length=100)
    language: str = Field(..., min_length=1, max_length=50)
    categories: List[str] = Field(..., min_length=1, max_length=20)
    keywords: Optional[List[str]] = Field(default=None, max_length=20)
    maximum_queries: Optional[int] = Field(None, ge=1, le=100)

    @field_validator("market", "language")
    @classmethod
    def clean_strings(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Value cannot be blank")
        return cleaned

    @field_validator("categories", "keywords")
    @classmethod
    def clean_lists(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned_list = []
        seen = set()
        for item in v:
            c = item.strip()
            if not c:
                continue
            if len(c) > 100:
                raise ValueError("List items must not exceed 100 characters")
            clower = c.lower()
            if clower not in seen:
                seen.add(clower)
                cleaned_list.append(c)
        return cleaned_list

    @field_validator("categories")
    @classmethod
    def require_categories(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one valid category is required")
        return v

class QueryGenerationResponse(BaseModel):
    queries: List[GeneratedSearchQuery]
    total: int

class SearchPreviewRequest(QueryGenerationRequest):
    results_per_query: int = Field(..., ge=1, le=20)
    provider: Optional[str] = Field(None, pattern="^(?i)(mock|brave|serper)$")

class SearchPreviewResponse(BaseModel):
    generated_queries: List[GeneratedSearchQuery]
    results: List[SearchResult]
    result_count: int
    provider: str
    errors: List[SearchPreviewError]

class NormalizedCandidate(BaseModel):
    original_url: str
    normalized_url: str
    homepage_url: str
    registered_domain: str
    subdomain: Optional[str] = None
    title: str
    snippet: Optional[str] = None
    query_text: str
    provider: str
    result_position: int
    market: Optional[str] = None
    language: Optional[str] = None

class RejectedCandidate(BaseModel):
    original_url: str
    query_text: str
    provider: str
    result_position: int
    reason_code: str
    safe_reason: str

class DuplicateCandidate(BaseModel):
    duplicate_url: str
    kept_url: str
    deduplication_key: str
    query_text: str
    result_position: int

class CandidateProcessingRequest(BaseModel):
    results: List[SearchResult]
    additional_blocked_domains: Optional[List[str]] = None

class CandidateProcessingResponse(BaseModel):
    accepted: List[NormalizedCandidate]
    rejected: List[RejectedCandidate]
    duplicates: List[DuplicateCandidate]
    accepted_count: int
    rejected_count: int
    duplicate_count: int

class CandidatePreviewRequest(SearchPreviewRequest):
    additional_blocked_domains: Optional[List[str]] = None
    include_rejected: bool = False
    include_duplicates: bool = False

class CandidatePreviewResponse(BaseModel):
    generated_queries: List[GeneratedSearchQuery]
    raw_result_count: int
    accepted_candidates: List[NormalizedCandidate]
    rejected_candidates: Optional[List[RejectedCandidate]] = None
    duplicates: Optional[List[DuplicateCandidate]] = None
    accepted_count: int
    rejected_count: int
    duplicate_count: int
    provider: str
    errors: List[SearchPreviewError]
