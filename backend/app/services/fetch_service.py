import asyncio
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import httpx
from datetime import datetime, timezone
import time

from app.config import get_settings
from app.schemas.search import NormalizedCandidate
from app.schemas.fetch import FetchRequest, FetchedPage, PageFetchPreview, FetchPreviewResponse
from app.schemas.acquisition import AcquisitionResult
from app.fetching.dns_resolver import DNSResolver
from app.fetching.fetch_orchestrator import FetchOrchestrator

def _convert_to_preview(page: FetchedPage, include_html: bool, max_chars: int) -> PageFetchPreview:
    html_preview = None
    preview_truncated = False
    
    if include_html and page.html:
        if len(page.html) > max_chars:
            html_preview = page.html[:max_chars]
            preview_truncated = True
        else:
            html_preview = page.html
            
    return PageFetchPreview(
        requested_url=page.requested_url,
        final_url=page.final_url,
        registered_domain=page.registered_domain,
        status_code=page.status_code,
        content_type=page.content_type,
        content_length=page.content_length,
        html_preview=html_preview,
        preview_truncated=preview_truncated,
        title=page.title,
        fetched_at=page.fetched_at,
        redirect_count=page.redirect_count,
        elapsed_ms=page.elapsed_ms,
        success=page.success,
        error_code=page.error_code,
        safe_error=page.safe_error
    )

class FetchService:
    def __init__(self):
        self.settings = get_settings()
        self.global_semaphore = asyncio.Semaphore(self.settings.MAX_FETCH_CONCURRENCY)
        self.host_semaphores: Dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self.settings.MAX_FETCHES_PER_HOST)
        )
        self.host_semaphores_lock = asyncio.Lock()
        
    async def get_host_semaphore(self, host: str) -> asyncio.Semaphore:
        async with self.host_semaphores_lock:
            return self.host_semaphores[host]

    async def acquire_evidence_batch(self, request: FetchRequest) -> Tuple[List[AcquisitionResult], int]:
        settings = self.settings
        candidates = request.candidates
        skipped_count = 0
        if request.maximum_candidates is not None and request.maximum_candidates > 0:
            if len(candidates) > request.maximum_candidates:
                skipped_count = len(candidates) - request.maximum_candidates
                candidates = candidates[:request.maximum_candidates]
                
        if len(candidates) > settings.MAX_FETCH_CANDIDATES:
            skipped_count += len(candidates) - settings.MAX_FETCH_CANDIDATES
            candidates = candidates[:settings.MAX_FETCH_CANDIDATES]

        dns_resolver = DNSResolver()
        transport = httpx.AsyncHTTPTransport(retries=0)
        limits = httpx.Limits(
            max_connections=settings.MAX_FETCH_CONCURRENCY,
            max_keepalive_connections=settings.MAX_FETCH_CONCURRENCY
        )
        timeout = httpx.Timeout(
            connect=settings.FETCH_CONNECT_TIMEOUT_SECONDS,
            read=settings.FETCH_READ_TIMEOUT_SECONDS,
            write=settings.FETCH_WRITE_TIMEOUT_SECONDS,
            pool=settings.FETCH_POOL_TIMEOUT_SECONDS
        )

        results: List[AcquisitionResult] = []

        # Add robust user agent and language
        headers = {
            "User-Agent": settings.FETCH_USER_AGENT,
            "Accept": "text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8,ja;q=0.7,fr;q=0.5"
        }

        async with httpx.AsyncClient(
            transport=transport,
            limits=limits,
            timeout=timeout,
            verify=True,
            follow_redirects=False,
            headers=headers
        ) as client:
            
            orchestrator = FetchOrchestrator(client, dns_resolver, settings)
            
            async def fetch_single(candidate: NormalizedCandidate) -> AcquisitionResult:
                url_to_fetch = candidate.homepage_url if request.use_homepage_url and candidate.homepage_url else candidate.normalized_url
                reg_domain = candidate.registered_domain
                
                host_sem = await self.get_host_semaphore(reg_domain)
                
                async def _inner():
                    async with self.global_semaphore:
                        async with host_sem:
                            return await orchestrator.acquire_evidence(url_to_fetch, candidate)
                            
                try:
                    res = await asyncio.wait_for(_inner(), timeout=settings.FETCH_TOTAL_TIMEOUT_SECONDS * 3) # Allow more time for fallbacks
                    return res
                except asyncio.TimeoutError:
                    return AcquisitionResult(
                        domain=reg_domain,
                        transport_success=False,
                        fetch_attempts=1,
                        primary_page=FetchedPage(
                            requested_url=url_to_fetch,
                            final_url=url_to_fetch,
                            registered_domain=reg_domain,
                            status_code=0,
                            fetched_at=datetime.now(timezone.utc),
                            success=False,
                            error_code="total_timeout",
                            safe_error="Fetch orchestrator exceeded timeout",
                            attempt_count=1
                        )
                    )
                except Exception as e:
                    return AcquisitionResult(
                        domain=reg_domain,
                        transport_success=False,
                        fetch_attempts=1,
                        primary_page=FetchedPage(
                            requested_url=url_to_fetch,
                            final_url=url_to_fetch,
                            registered_domain=reg_domain,
                            status_code=0,
                            fetched_at=datetime.now(timezone.utc),
                            success=False,
                            error_code="unexpected_fetch_error",
                            safe_error=f"Unexpected orchestrator failure: {e}",
                            attempt_count=1
                        )
                    )

            tasks = [fetch_single(c) for c in candidates]
            fetched = await asyncio.gather(*tasks, return_exceptions=True)
            
            for item in fetched:
                if isinstance(item, Exception):
                    pass
                else:
                    results.append(item)
                    
        return results, skipped_count

    async def fetch_pages(self, request: FetchRequest) -> Tuple[List[FetchedPage], int]:
        acquisition_results, skipped_count = await self.acquire_evidence_batch(request)
        pages = []
        for acq in acquisition_results:
            if acq.primary_page:
                pages.append(acq.primary_page)
            pages.extend(acq.supporting_pages)
        return pages, skipped_count

    async def fetch_preview(self, request: FetchRequest) -> FetchPreviewResponse:
        acquisition_results, skipped_count = await self.acquire_evidence_batch(request)
        
        previews: List[PageFetchPreview] = []
        for acq in acquisition_results:
            if acq.primary_page:
                previews.append(_convert_to_preview(acq.primary_page, request.include_html_preview, self.settings.FETCH_PREVIEW_MAX_CHARS))
                
        success_count = sum(1 for p in previews if p.success)
        failure_count = len(previews) - success_count
        
        return FetchPreviewResponse(
            results=previews,
            success_count=success_count,
            failure_count=failure_count,
            skipped_count=skipped_count
        )
