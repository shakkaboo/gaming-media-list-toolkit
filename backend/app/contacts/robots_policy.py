import urllib.robotparser
from urllib.parse import urlparse, urljoin
from typing import Dict, Optional
from dataclasses import dataclass

from app.config import get_settings
from app.services.fetch_service import FetchService
from app.schemas.fetch import FetchRequest
from app.schemas.search import NormalizedCandidate

@dataclass(frozen=True)
class RobotsDecision:
    allowed: bool
    status: str
    error_code: Optional[str] = None
    safe_error: Optional[str] = None

class RobotsPolicyChecker:
    def __init__(self, fetch_service: FetchService):
        self.settings = get_settings()
        self.fetch_service = fetch_service
        self.cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self.failure_policy = self.settings.ROBOTS_FAILURE_POLICY
        self.user_agent = self.settings.FETCH_USER_AGENT

    async def is_allowed(self, target_url: str) -> RobotsDecision:
        parsed = urlparse(target_url)
        if not parsed.scheme or not parsed.netloc:
            return RobotsDecision(allowed=False, status="invalid_url", error_code="invalid_url", safe_error="Invalid URL")
            
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = urljoin(base_url, "/robots.txt")

        if base_url in self.cache:
            parser = self.cache[base_url]
            if parser is None:
                allowed = self.failure_policy == "allow"
                return RobotsDecision(allowed=allowed, status="cached_failure", error_code="cached_failure", safe_error="Cached fetch failure")
            allowed = parser.can_fetch(self.user_agent, target_url)
            return RobotsDecision(allowed=allowed, status="allowed" if allowed else "disallowed")

        candidate = NormalizedCandidate(
            requested_url=robots_url,
            normalized_url=robots_url,
            homepage_url=base_url,
            registered_domain=parsed.netloc,
            original_url=robots_url,
            title="",
            query_text="",
            provider="",
            result_position=1
        )
        
        req = FetchRequest(
            candidates=[candidate],
            maximum_candidates=1,
            use_homepage_url=False,
            include_html_preview=False,
            allowed_content_types=["text/plain"],
            max_response_bytes=self.settings.MAX_ROBOTS_RESPONSE_BYTES
        )
        
        pages, _ = await self.fetch_service.fetch_pages(req)
        if not pages:
            self.cache[base_url] = None
            allowed = self.failure_policy == "allow"
            return RobotsDecision(allowed=allowed, status="fetch_empty", error_code="fetch_empty", safe_error="No page returned")
            
        page = pages[0]
        
        if page.success:
            final_parsed = urlparse(page.final_url)
            if final_parsed.netloc != parsed.netloc:
                # off-domain redirect
                self.cache[base_url] = None
                return RobotsDecision(allowed=False, status="off_domain_redirect", error_code="off_domain_redirect", safe_error="Off-domain redirect for robots.txt")
                
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robots_url)
            lines = (page.html or "").splitlines()
            parser.parse(lines)
            self.cache[base_url] = parser
            allowed = parser.can_fetch(self.user_agent, target_url)
            return RobotsDecision(
                allowed=allowed,
                status="allowed" if allowed else "disallowed",
                error_code=None,
                safe_error=None
            )
            
        if page.status_code in (404, 410):
            return RobotsDecision(
                allowed=True,
                status="not_found",
            )
            
        if page.status_code in (401, 403):
            return RobotsDecision(
                allowed=False,
                status="denied",
                error_code="robots_access_denied",
                safe_error="The robots policy could not be accessed.",
            )

        if (
            page.status_code == 429
            or page.status_code >= 500
            or page.error_code in {
                "dns_failed",
                "dns_timeout",
                "connection_timeout",
                "read_timeout",
                "connection_error",
            }
        ):
            allowed = self.failure_policy == "allow"
            return RobotsDecision(
                allowed=allowed,
                status="unavailable",
                error_code=page.error_code or "robots_unavailable",
                safe_error="The robots policy was unavailable.",
            )
            
        # Handle all other errors
        self.cache[base_url] = None
        allowed = self.failure_policy == "allow"
        return RobotsDecision(allowed=allowed, status="fetch_failed", error_code="fetch_failed", safe_error=f"Fetch failed: {page.error_code}")
