from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.search import NormalizedCandidate

class FetchedPage(BaseModel):
    requested_url: str
    final_url: str
    registered_domain: str
    status_code: int
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    html: Optional[str] = None
    title: Optional[str] = None
    fetched_at: datetime
    redirect_chain: List[str] = []
    redirect_count: int = 0
    elapsed_ms: int = 0
    success: bool
    error_code: Optional[str] = None
    safe_error: Optional[str] = None
    fetch_method: str = "http"
    failure_category: Optional[str] = None
    failure_reason: Optional[str] = None
    challenge_detected: bool = False
    javascript_shell_detected: bool = False
    robots_disallowed: bool = False
    attempt_count: int = 1

class PageFetchPreview(BaseModel):
    requested_url: str
    final_url: str
    registered_domain: str
    status_code: int
    content_type: Optional[str]
    content_length: Optional[int]
    html_preview: Optional[str] = None
    preview_truncated: bool = False
    title: Optional[str]
    fetched_at: datetime
    redirect_count: int
    elapsed_ms: int
    success: bool
    error_code: Optional[str]
    safe_error: Optional[str]

class FetchRequest(BaseModel):
    candidates: List[NormalizedCandidate]
    maximum_candidates: Optional[int] = None
    use_homepage_url: bool = True
    include_html_preview: bool = False
    allowed_content_types: Optional[List[str]] = None
    max_response_bytes: Optional[int] = None

class FetchPreviewResponse(BaseModel):
    results: List[PageFetchPreview]
    success_count: int
    failure_count: int
    skipped_count: int
