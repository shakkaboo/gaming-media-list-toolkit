import asyncio
import time
from typing import List, Optional, Set
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime, timezone

from app.config import get_settings
from app.schemas.search import NormalizedCandidate
from app.schemas.fetch import FetchedPage
from app.schemas.acquisition import AcquisitionResult, FeedEntry, SitemapCandidate
from app.fetching.page_fetcher import fetch_page_with_retries
from app.fetching.dns_resolver import DNSResolver

class FetchOrchestrator:
    def __init__(self, client, dns_resolver: DNSResolver, settings):
        self.client = client
        self.dns_resolver = dns_resolver
        self.settings = settings

    async def acquire_evidence(self, url: str, candidate: NormalizedCandidate) -> AcquisitionResult:
        result = AcquisitionResult(domain=candidate.registered_domain)
        
        # 1. Standard HTTP Fetch (Canonical Variants)
        variants = self._generate_canonical_variants(url)
        primary_page = None
        for variant in variants:
            if result.fetch_attempts >= 5:
                break
                
            page = await fetch_page_with_retries(
                variant, self.client, self.dns_resolver, self.settings
            )
            result.fetch_attempts += getattr(page, 'attempt_count', 1)
            result.transport_success = page.success
            
            if page.success:
                primary_page = page
                result.primary_page = page
                break
            else:
                # Store the failure so we have a record
                if not result.primary_page:
                    result.primary_page = page
                # If HTTPS fails due to connection or SSL error, we try HTTP next if available
                # If it's a 404, we don't need to try HTTP unless we want to try "www."

        if not primary_page:
            return result

        # 2. Check usable evidence for standard HTML
        if primary_page.success and primary_page.html and len(primary_page.html) > 100:
            if not getattr(primary_page, 'javascript_shell_detected', False) and not getattr(primary_page, 'challenge_detected', False):
                result.usable_evidence_found = True

        # 3. Playwright Fallback
        if not result.usable_evidence_found and result.fetch_attempts < 5:
            # Only attempt playwright if it's a JS shell or insufficient content. 
            # NOT if explicit challenge or block.
            cat = getattr(primary_page, 'failure_category', None)
            if cat not in ("http_401", "http_403", "http_404", "challenge_page", "robots_disallowed"):
                # Attempt Playwright
                try:
                    pw_page = await self._fetch_playwright(primary_page.final_url)
                    result.fetch_attempts += 1
                    if pw_page and pw_page.success:
                        pw_page.fetch_method = "playwright"
                        result.primary_page = pw_page
                        if pw_page.html and len(pw_page.html) > 100:
                            result.usable_evidence_found = True
                            result.transport_success = True
                except Exception:
                    pass

        # 4. RSS / Sitemap Fallbacks
        if not result.usable_evidence_found and result.fetch_attempts < 5:
            await self._discover_alternate_evidence(result)

        return result

    def _generate_canonical_variants(self, url: str) -> List[str]:
        parsed = urlparse(url)
        host = parsed.netloc
        scheme = parsed.scheme
        path = parsed.path or "/"
        
        variants = []
        if scheme == "https":
            variants.append(url)
            if host.startswith("www."):
                variants.append(f"https://{host[4:]}{path}")
            else:
                variants.append(f"https://www.{host}{path}")
            # Add HTTP fallback
            variants.append(f"http://{host}{path}")
        else:
            variants.append(url)
            variants.append(f"https://{host}{path}")
            
        # Deduplicate
        seen = set()
        unique_variants = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                unique_variants.append(v)
        return unique_variants[:3]

    async def _fetch_playwright(self, url: str) -> Optional[FetchedPage]:
        # Implement Playwright headless fetch
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.settings.FETCH_USER_AGENT
                )
                page = await context.new_page()
                
                # Block images, media, fonts
                await page.route("**/*", lambda route: route.continue_() if route.request.resource_type in ["document", "script", "xhr", "fetch"] else route.abort())
                
                start = time.monotonic()
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=self.settings.FETCH_TOTAL_TIMEOUT_SECONDS * 1000)
                html = await page.content()
                elapsed_ms = int((time.monotonic() - start) * 1000)
                
                await browser.close()
                
                return FetchedPage(
                    requested_url=url,
                    final_url=resp.url if resp else url,
                    registered_domain="",
                    status_code=resp.status if resp else 0,
                    content_type="text/html",
                    content_length=len(html),
                    html=html,
                    title=await page.title(),
                    fetched_at=datetime.now(timezone.utc),
                    redirect_chain=[],
                    redirect_count=0,
                    elapsed_ms=elapsed_ms,
                    success=True,
                    error_code=None,
                    safe_error=None,
                    fetch_method="playwright",
                    failure_category=None,
                    failure_reason=None,
                    challenge_detected=False,
                    javascript_shell_detected=False,
                    robots_disallowed=False
                )
        except ImportError:
            return None
        except Exception as e:
            return None

    async def _discover_alternate_evidence(self, result: AcquisitionResult):
        if result.fetch_attempts >= 5:
            return

        domain = result.domain
        if not domain:
            return

        sitemap_url = f"https://{domain}/sitemap.xml"
        try:
            sitemap_page = await fetch_page_with_retries(sitemap_url, self.client, self.dns_resolver, self.settings)
            result.fetch_attempts += getattr(sitemap_page, 'attempt_count', 1)
            
            if sitemap_page.success and sitemap_page.html:
                soup = BeautifulSoup(sitemap_page.html, "xml")
                locs = soup.find_all("loc")
                keywords = ["article", "news", "review", "post", "レビュー", "ニュース"]
                candidates = []
                for loc in locs:
                    u = loc.text.strip()
                    if any(k in u.lower() for k in keywords):
                        candidates.append(u)
                        
                for c_url in candidates[:2]:
                    if result.fetch_attempts >= 5:
                        break
                        
                    c_page = await fetch_page_with_retries(c_url, self.client, self.dns_resolver, self.settings)
                    result.fetch_attempts += getattr(c_page, 'attempt_count', 1)
                    
                    if c_page.success and c_page.html and len(c_page.html) > 100:
                        c_page.fetch_method = "http_sitemap"
                        result.supporting_pages.append(c_page)
                        result.usable_evidence_found = True
                        result.transport_success = True
                        break
        except Exception:
            pass
