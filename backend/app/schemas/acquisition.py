from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.fetch import FetchedPage

class FeedEntry(BaseModel):
    title: Optional[str] = None
    url: str
    published_at: Optional[datetime] = None
    summary: Optional[str] = None

class SitemapCandidate(BaseModel):
    url: str
    last_modified: Optional[datetime] = None

class AcquisitionResult(BaseModel):
    domain: str
    primary_page: Optional[FetchedPage] = None
    supporting_pages: List[FetchedPage] = []
    feed_entries: List[FeedEntry] = []
    sitemap_candidates: List[SitemapCandidate] = []
    fetch_attempts: int = 0
    transport_success: bool = False
    usable_evidence_found: bool = False
