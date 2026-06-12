import asyncio
from typing import List, Optional, Tuple
from datetime import datetime, timezone

from app.config import get_settings
from app.schemas.search import NormalizedCandidate
from app.schemas.fetch import FetchRequest, FetchedPage
from app.schemas.verification import VerificationResult, VerificationRequest
from app.schemas.contact_discovery import (
    ContactDiscoveryRequest, ContactDiscoveryResult, ContactDiscoveryPreviewResponse,
    ContactPageCandidate, ExtractedContact, ContactForm, ContactEvidence
)
from app.services.fetch_service import FetchService
from app.services.verification_service import VerificationService
from app.contacts.link_discovery import LinkDiscoverer
from app.contacts.robots_policy import RobotsPolicyChecker
from app.contacts.email_extractor import EmailExtractor
from app.contacts.form_detector import FormDetector
from app.contacts.contact_classifier import ContactClassifier
from app.contacts.deduplicator import Deduplicator

class ContactService:
    def __init__(self):
        self.settings = get_settings()
        self.fetch_service = FetchService()
        self.verification_service = VerificationService()
        self.link_discoverer = LinkDiscoverer()
        self.robots_checker = RobotsPolicyChecker(self.fetch_service)
        self.email_extractor = EmailExtractor()
        self.form_detector = FormDetector()
        self.classifier = ContactClassifier()
        self.deduplicator = Deduplicator()

    async def discover_contacts_batch(self, request: ContactDiscoveryRequest) -> ContactDiscoveryPreviewResponse:
        candidates = request.candidates
        limit = request.maximum_candidates or self.settings.MAX_CONTACT_CANDIDATES
        
        skipped_count = 0
        if len(candidates) > limit:
            skipped_count = len(candidates) - limit
            candidates = candidates[:limit]
            
        results: List[ContactDiscoveryResult] = []
        
        # Concurrency limit for the overall site discovery
        sem = asyncio.Semaphore(self.settings.MAX_CONTACT_CONCURRENCY)
        
        async def process_candidate(candidate: NormalizedCandidate) -> ContactDiscoveryResult:
            async with sem:
                try:
                    return await asyncio.wait_for(
                        self.discover_contacts_for_site(
                            candidate=candidate,
                            allow_uncertain=request.allow_uncertain,
                            maximum_pages=request.maximum_pages_per_site,
                            include_named_contacts=request.include_named_contacts
                        ),
                        timeout=self.settings.CONTACT_DISCOVERY_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    return self._create_error_result(candidate, "contact_discovery_timeout", "Site processing exceeded timeout")
                except Exception as e:
                    return self._create_error_result(candidate, "unexpected_contact_error", f"Unexpected failure: {str(e)}")

        tasks = [process_candidate(c) for c in candidates]
        processed = await asyncio.gather(*tasks)
        
        results.extend(processed)
        
        sites_processed = len(results)
        sites_with_contacts = sum(1 for r in results if r.success and (len(r.contacts) > 0 or len(r.forms) > 0))
        contacts_found = sum(len(r.contacts) for r in results)
        forms_found = sum(len(r.forms) for r in results)
        failed_count = sum(1 for r in results if not r.success)
        
        return ContactDiscoveryPreviewResponse(
            results=results,
            sites_processed=sites_processed,
            sites_with_contacts=sites_with_contacts,
            contacts_found=contacts_found,
            forms_found=forms_found,
            skipped_count=skipped_count,
            failed_count=failed_count
        )

    async def discover_from_verified_site(
        self, 
        candidate: NormalizedCandidate, 
        homepage_page: FetchedPage, 
        verification_result: VerificationResult,
        allow_uncertain: bool,
        maximum_pages: Optional[int] = None,
        include_named_contacts: bool = False
    ) -> ContactDiscoveryResult:
        """Internal variant for Phase 3F reuse."""
        return await self._execute_discovery(
            candidate, homepage_page, verification_result, allow_uncertain, maximum_pages, include_named_contacts
        )

    async def discover_contacts_for_site(
        self, 
        candidate: NormalizedCandidate, 
        allow_uncertain: bool = False,
        maximum_pages: Optional[int] = None,
        include_named_contacts: bool = False
    ) -> ContactDiscoveryResult:
        # Step 1: Fetch homepage
        fetch_req = FetchRequest(
            candidates=[candidate],
            maximum_candidates=1,
            use_homepage_url=True,
            include_html_preview=False
        )
        pages, _ = await self.fetch_service.fetch_pages(fetch_req)
        if not pages:
            return self._create_error_result(candidate, "homepage_fetch_failed", "No page returned")
            
        homepage_page = pages[0]
        if not homepage_page.success:
            return self._create_error_result(candidate, "homepage_fetch_failed", homepage_page.safe_error or "Fetch failed")
            
        # Step 2: Verification
        vreq = VerificationRequest(candidates=[candidate])
        v_result = await asyncio.to_thread(
            self.verification_service._verify_page_sync, homepage_page, datetime.now(timezone.utc), vreq
        )
        
        return await self._execute_discovery(
            candidate, homepage_page, v_result, allow_uncertain, maximum_pages, include_named_contacts
        )

    async def _execute_discovery(
        self, 
        candidate: NormalizedCandidate, 
        homepage_page: FetchedPage, 
        verification_result: VerificationResult,
        allow_uncertain: bool,
        maximum_pages: Optional[int],
        include_named_contacts: bool
    ) -> ContactDiscoveryResult:
        
        # Gating
        v_status = verification_result.verification_status
        if v_status == "rejected":
            return self._create_error_result(candidate, "rejected_candidate", "Candidate is rejected")
        if v_status == "uncertain" and not allow_uncertain:
            return self._create_error_result(candidate, "verification_required", "Candidate is uncertain")
        if v_status == "fetch_failed":
            return self._create_error_result(candidate, "verification_failed", "Homepage fetch failed during verification")
            
        # Step 3: Link Discovery
        target_links = await asyncio.to_thread(
            self.link_discoverer.discover_links, homepage_page.html, homepage_page.final_url, candidate
        )
        
        max_p = maximum_pages or self.settings.MAX_CONTACT_PAGES_PER_SITE
        if len(target_links) > max_p:
            target_links = target_links[:max_p]
            
        # If no explicit links, we should at least parse the homepage
        if not target_links:
            target_links = [ContactPageCandidate(
                url=homepage_page.final_url,
                page_type='contact', # Assume homepage serves as general contact
                score=0,
                discovery_order=0
            )]
            
        # Step 4: Fetch target pages concurrently (respecting robots.txt)
        fetched_pages = []
        page_errors = []
        
        # Check robots for each URL
        # We process sequentially or concurrently. Let's do concurrently.
        async def fetch_target(target: ContactPageCandidate) -> Optional[Tuple[ContactPageCandidate, FetchedPage]]:
            decision = await self.robots_checker.is_allowed(target.url)
            
            if decision.status == "disallowed":
                page_errors.append(f"{target.url}: page_disallowed_by_robots")
                return None
                
            if not decision.allowed and decision.status in {"denied", "unavailable"}:
                page_errors.append(f"{target.url}: robots_unavailable")
                return None
                
            # fetch
            req = FetchRequest(
                candidates=[NormalizedCandidate(requested_url=target.url, normalized_url=target.url, homepage_url=homepage_page.final_url, registered_domain=candidate.registered_domain, subdomain=candidate.subdomain, original_url=target.url, title="", query_text="", provider="", result_position=1)],
                use_homepage_url=False,
                allowed_content_types=["text/html", "application/xhtml+xml"],
                max_response_bytes=self.settings.MAX_CONTACT_HTML_RESPONSE_BYTES
            )
            try:
                # Wrap in timeout for the individual page
                p, _ = await asyncio.wait_for(self.fetch_service.fetch_pages(req), timeout=self.settings.CONTACT_PAGE_FETCH_TIMEOUT_SECONDS)
                if p and p[0].success:
                    return (target, p[0])
                else:
                    if p:
                        page_errors.append(f"{target.url}: {p[0].error_code}")
                    else:
                        page_errors.append(f"{target.url}: contact_page_fetch_failed")
            except asyncio.TimeoutError:
                page_errors.append(f"{target.url}: page_timeout")
            except Exception as e:
                page_errors.append(f"{target.url}: extraction_failed")
            return None
            
        # If the target is the homepage, don't refetch
        targets_to_fetch = []
        for t in target_links:
            if t.url == homepage_page.final_url:
                fetched_pages.append((t, homepage_page))
            else:
                targets_to_fetch.append(t)
                
        fetch_tasks = [fetch_target(t) for t in targets_to_fetch]
        if fetch_tasks:
            results = await asyncio.gather(*fetch_tasks)
            for r in results:
                if r:
                    fetched_pages.append(r)
                    
        # Step 5: Extraction
        all_emails = []
        all_forms = []
        
        def extract_page(target: ContactPageCandidate, page: FetchedPage):
            html = page.html or ""
            emails = self.email_extractor.extract_from_html(html, target.url, target.page_type, target.discovery_order)
            forms = self.form_detector.detect_forms(html, target.url, candidate.registered_domain)
            return emails, forms
            
        for target, page in fetched_pages:
            try:
                emails, forms = await asyncio.to_thread(extract_page, target, page)
                all_emails.extend(emails)
                all_forms.extend(forms)
            except Exception as e:
                page_errors.append(f"{target.url}: extraction_failed")
                
        # Step 6: Classification
        classified_emails = []
        for em in all_emails:
            if not include_named_contacts and em.is_named_contact:
                continue
            classified = self.classifier.classify(em)
            classified_emails.append(classified)
            
        # Step 7: Deduplication and Ranking
        final_contacts = self.deduplicator.deduplicate_and_rank_contacts(classified_emails, candidate.registered_domain, homepage_page.final_url)
        final_forms = self.deduplicator.deduplicate_forms(all_forms)
        
        best_contact = final_contacts[0] if final_contacts else None
        
        # Check robots status
        robots_status = "allowed" if self.settings.ROBOTS_FAILURE_POLICY == "allow" else "checked"
        
        return ContactDiscoveryResult(
            candidate_url=candidate.normalized_url,
            registered_domain=candidate.registered_domain,
            verification_status=v_status,
            pages_considered=len(target_links),
            pages_fetched=len(fetched_pages),
            page_errors=page_errors,
            robots_status=robots_status,
            contacts=final_contacts,
            forms=final_forms,
            best_contact=best_contact,
            success=True,
            error_code=None,
            safe_error=None
        )

    def _create_error_result(self, candidate: NormalizedCandidate, code: str, msg: str) -> ContactDiscoveryResult:
        return ContactDiscoveryResult(
            candidate_url=candidate.normalized_url,
            registered_domain=candidate.registered_domain,
            verification_status="unknown",
            pages_considered=0,
            pages_fetched=0,
            page_errors=[],
            robots_status="unknown",
            contacts=[],
            forms=[],
            best_contact=None,
            success=False,
            error_code=code,
            safe_error=msg
        )