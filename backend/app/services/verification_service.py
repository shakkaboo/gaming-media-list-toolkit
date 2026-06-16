import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from app.config import get_settings
from app.schemas.search import NormalizedCandidate
from app.schemas.fetch import FetchRequest, FetchedPage
from app.schemas.verification import (
    VerificationRequest,
    VerificationPreviewResponse,
    VerificationResult,
    VerificationReason,
    V2ShadowResult,
)
from app.services.fetch_service import FetchService
from app.verification.html_analyzer import HtmlAnalyzer
from app.verification.classifier import Classifier, CLASSIFIER_VERSION

class VerificationService:
    def __init__(self):
        self.settings = get_settings()
        self.fetch_service = FetchService()
        self.classifier = Classifier(self.settings)
        self.concurrency_sem = asyncio.Semaphore(self.settings.MAX_VERIFICATION_CONCURRENCY)

    def _verify_page_sync(self, page: FetchedPage, current_time: datetime, request: VerificationRequest) -> VerificationResult:
        if not page.success:
            return VerificationResult(
                requested_url=page.requested_url,
                final_url=page.final_url,
                registered_domain=page.registered_domain,
                score=0,
                verification_status="fetch_failed",
                confidence=0.0,
                gaming_relevance_score=0,
                editorial_structure_score=0,
                activity_score=0,
                publication_identity_score=0,
                negative_penalty=0,
                positive_reasons=[],
                negative_reasons=[
                    VerificationReason(
                        code="fetch_failed", 
                        message="Could not fetch the page", 
                        weight=-100, 
                        evidence=[page.error_code or "unknown error"]
                    )
                ],
                detected_categories=[],
                activity_status="unknown",
                newest_detected_publication_date=None,
                article_count_estimate=0,
                classifier_version=CLASSIFIER_VERSION,
                analysed_at=datetime.now(timezone.utc),
                fetch_success=False,
                fetch_error_code=page.error_code,
                safe_error=page.safe_error,
                market_evidence=[]
            )

        html = page.html or ""
        analyzer = HtmlAnalyzer(html)
        signals = analyzer.analyze()
        
        return self.classifier.classify(
            requested_url=page.requested_url,
            final_url=page.final_url,
            registered_domain=page.registered_domain,
            signals=signals,
            current_time=current_time,
            verified_threshold_override=request.verified_threshold,
            uncertain_threshold_override=request.uncertain_threshold
        )

    async def verify_candidates(self, request: VerificationRequest, current_time: datetime = None) -> VerificationPreviewResponse:
        if current_time is None:
            current_time = datetime.now(timezone.utc)
            
        candidates = request.candidates
        limit = self.settings.MAX_VERIFICATION_CANDIDATES
        if request.maximum_candidates and request.maximum_candidates > 0:
            limit = min(limit, request.maximum_candidates)
            
        skipped_count = 0
        if len(candidates) > limit:
            skipped_count = len(candidates) - limit
            candidates = candidates[:limit]

        fetch_req = FetchRequest(
            candidates=candidates,
            maximum_candidates=limit,
            use_homepage_url=True,
            include_html_preview=False
        )
        
        acq_results, fetch_skipped = await self.fetch_service.acquire_evidence_batch(fetch_req)
        skipped_count += fetch_skipped

        results: List[VerificationResult] = []
        v2_results = []

        classifier_mode = getattr(request, "classifier_version", "baseline")
        use_v2 = classifier_mode == "v2_multilingual_explainable"
        use_shadow = classifier_mode == "v2_shadow"

        if use_shadow:
            from app.verification.classifier_v2 import ClassifierV2
            classifier_v2 = ClassifierV2(self.settings)

            async def process_shadow(acq):
                async with self.concurrency_sem:
                    url = (acq.primary_page.requested_url if acq.primary_page
                           else f"https://{acq.domain}/")

                    # Production decision: baseline on primary page only
                    if acq.primary_page:
                        try:
                            baseline_res = await asyncio.wait_for(
                                asyncio.to_thread(
                                    self._verify_page_sync, acq.primary_page, current_time, request),
                                timeout=self.settings.VERIFICATION_TIMEOUT_SECONDS
                            )
                        except asyncio.TimeoutError:
                            baseline_res = self._create_error_result(
                                acq.primary_page, "analysis_timeout",
                                "Verification exceeded CPU timeout")
                        except Exception as exc:
                            baseline_res = self._create_error_result(
                                acq.primary_page, "analysis_error", str(exc))
                    else:
                        from app.schemas.fetch import FetchedPage as _FP
                        synthetic = _FP(
                            requested_url=url, final_url=url,
                            registered_domain=acq.domain,
                            status_code=0,
                            fetched_at=datetime.now(timezone.utc),
                            success=False,
                            error_code="no_primary_page",
                        )
                        baseline_res = self._verify_page_sync(synthetic, current_time, request)

                    # Shadow: run v2 (result stored for review, not returned as production)
                    v2_res = None
                    try:
                        v2_res = await asyncio.wait_for(
                            asyncio.to_thread(
                                classifier_v2.classify_acquisition, acq, current_time, request),
                            timeout=self.settings.VERIFICATION_TIMEOUT_SECONDS
                        )
                    except Exception:
                        pass

                    if v2_res is not None:
                        b_status = baseline_res.verification_status
                        v2_status = v2_res.predicted_status
                        if v2_status == "uncertain":
                            rec = "v2_abstained"
                        elif b_status == "verified" and v2_status == "verified":
                            rec = "agree"
                        elif b_status == "rejected" and v2_status == "rejected":
                            rec = "agree"
                        elif v2_status == "verified":
                            rec = "review_v2_positive"
                        elif v2_status == "rejected":
                            rec = "review_v2_negative"
                        else:
                            rec = "review"

                        baseline_res.v2_shadow = V2ShadowResult(
                            v2_predicted_status=v2_status,
                            v2_relevance_label=v2_res.relevance_label,
                            v2_market_status=v2_res.market_status,
                            gaming_score=v2_res.gaming_score,
                            media_score=v2_res.media_score,
                            market_score=v2_res.market_score,
                            activity_score=v2_res.activity_score,
                            technical_score=v2_res.technical_score,
                            component_sum=v2_res.component_sum,
                            contextual_deductions=v2_res.contextual_deductions,
                            total_score=v2_res.total_score,
                            hard_rejection_rule=v2_res.hard_rejection_rule,
                            hard_rejection_evidence=list(v2_res.hard_rejection_evidence),
                            decision_override=v2_res.decision_override,
                            v2_explanation=v2_res.decision_reason,
                            review_recommendation=rec,
                        )

                    return baseline_res

            shadow_tasks = [process_shadow(acq) for acq in acq_results]
            processed_shadow = await asyncio.gather(*shadow_tasks)
            shadow_results = [r for r in processed_shadow if r is not None]

            return VerificationPreviewResponse(
                results=shadow_results,
                verified_count=sum(1 for r in shadow_results if r.verification_status == "verified"),
                uncertain_count=sum(1 for r in shadow_results if r.verification_status == "uncertain"),
                rejected_count=sum(1 for r in shadow_results if r.verification_status == "rejected"),
                failed_count=sum(1 for r in shadow_results if not r.fetch_success),
                skipped_count=skipped_count,
            )

        elif use_v2:
            from app.verification.classifier_v2 import ClassifierV2
            classifier_v2 = ClassifierV2(self.settings)
            
            async def process_acq(acq):
                async with self.concurrency_sem:
                    try:
                        return await asyncio.wait_for(
                            asyncio.to_thread(classifier_v2.classify_acquisition, acq, current_time, request),
                            timeout=self.settings.VERIFICATION_TIMEOUT_SECONDS
                        )
                    except Exception as e:
                        return None
            
            tasks = [process_acq(acq) for acq in acq_results]
            processed_results = await asyncio.gather(*tasks)
            v2_results = [r for r in processed_results if r]
            
            # Count for v2 preview response (it returns VerificationResultV2 but we can just duck-type the response)
            verified_count = sum(1 for r in v2_results if r.predicted_status == "verified")
            uncertain_count = sum(1 for r in v2_results if r.predicted_status == "uncertain")
            rejected_count = sum(1 for r in v2_results if r.predicted_status == "rejected")
            failed_count = sum(1 for r in v2_results if not r.fetch_success)
            
            return VerificationPreviewResponse(
                results=v2_results,  # This will serialize VerificationResultV2 fine if we add it to the union, but for now we'll just return it. Actually VerificationPreviewResponse says List[VerificationResult]. We might need to override the type or just let pydantic duck-type it? Wait, Pydantic will complain.
                verified_count=verified_count,
                uncertain_count=uncertain_count,
                rejected_count=rejected_count,
                failed_count=failed_count,
                skipped_count=skipped_count
            )

        else:
            pages = []
            for acq in acq_results:
                if acq.primary_page:
                    pages.append(acq.primary_page)
                pages.extend(acq.supporting_pages)
                
            async def process_page(p: FetchedPage) -> VerificationResult:
                async with self.concurrency_sem:
                    try:
                        return await asyncio.wait_for(
                            asyncio.to_thread(self._verify_page_sync, p, current_time, request),
                            timeout=self.settings.VERIFICATION_TIMEOUT_SECONDS
                        )
                    except asyncio.TimeoutError:
                        return self._create_error_result(p, "analysis_timeout", "Verification exceeded CPU timeout")
                    except Exception as e:
                        return self._create_error_result(p, "analysis_error", f"Unexpected verification failure: {e}")

            tasks = [process_page(p) for p in pages]
            processed_results = await asyncio.gather(*tasks)
            
            verified_count = 0
            uncertain_count = 0
            rejected_count = 0
            failed_count = 0
            
            for res in processed_results:
                if request.expected_market:
                    res.expected_market = request.expected_market
                if request.expected_language:
                    res.expected_language = request.expected_language
                    
                if not request.include_evidence:
                    for r in res.positive_reasons + res.negative_reasons:
                        r.evidence = []
                        
                if res.verification_status == "verified": verified_count += 1
                elif res.verification_status == "uncertain": uncertain_count += 1
                elif res.verification_status == "rejected": rejected_count += 1
                elif res.verification_status == "fetch_failed": failed_count += 1
                
                results.append(res)
                
            return VerificationPreviewResponse(
                results=results,
                verified_count=verified_count,
                uncertain_count=uncertain_count,
                rejected_count=rejected_count,
                failed_count=failed_count,
                skipped_count=skipped_count
            )

    def _create_error_result(self, page: FetchedPage, code: str, msg: str) -> VerificationResult:
        return VerificationResult(
            requested_url=page.requested_url,
            final_url=page.final_url,
            registered_domain=page.registered_domain,
            score=0,
            verification_status="fetch_failed",
            confidence=0.0,
            gaming_relevance_score=0,
            editorial_structure_score=0,
            activity_score=0,
            publication_identity_score=0,
            negative_penalty=0,
            positive_reasons=[],
            negative_reasons=[
                VerificationReason(code=code, message=msg, weight=-100, evidence=[])
            ],
            detected_categories=[],
            activity_status="unknown",
            newest_detected_publication_date=None,
            article_count_estimate=0,
            classifier_version=CLASSIFIER_VERSION,
            analysed_at=datetime.now(timezone.utc),
            fetch_success=page.success,
            fetch_error_code=page.error_code,
            safe_error=msg,
            market_evidence=[]
        )
