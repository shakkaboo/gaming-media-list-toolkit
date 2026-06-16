from datetime import datetime, timezone
from typing import List, Optional

from app.schemas.verification import (
    ExtractedSiteSignals,
    VerificationResultV2,
    VerificationReason,
    VerificationRequest
)
from app.schemas.acquisition import AcquisitionResult
from app.verification.html_analyzer import HtmlAnalyzer
from app.verification.rules_v2 import (
    normalize_evidence,
    score_gaming_relevance,
    score_media_evidence,
    score_market_relevance,
    score_activity,
    score_technical,
    compute_deductions_and_hard_rejections,
    VOCABULARY_VERSION
)

CLASSIFIER_VERSION = "v2_multilingual_explainable"

class ClassifierV2:
    def __init__(self, settings):
        self.settings = settings
        
    def classify_acquisition(self, acq: AcquisitionResult, current_time: datetime, request: VerificationRequest) -> VerificationResultV2:
        if not acq.usable_evidence_found or not acq.transport_success:
            return VerificationResultV2(
                requested_url=acq.primary_page.requested_url if acq.primary_page else "",
                final_url=acq.primary_page.final_url if acq.primary_page else "",
                registered_domain=acq.domain,
                classifier_version=CLASSIFIER_VERSION,
                gaming_score=0,
                media_score=0,
                market_score=0,
                activity_score=0,
                technical_score=0,
                component_sum=0,
                contextual_deductions=0,
                total_score=0,
                predicted_status="uncertain",  # Fetch failure means uncertain, not rejected automatically
                relevance_label="uncertain",
                market_status="unconfirmed",
                decision_reason="Fetch failed, no usable evidence acquired.",
                evidence=normalize_evidence([], request.expected_language, request.expected_market),
                analysed_at=datetime.now(timezone.utc),
                fetch_success=False,
                fetch_error_code=acq.primary_page.error_code if acq.primary_page else "unknown",
            )
            
        signals_list: List[ExtractedSiteSignals] = []
        pages = []
        if acq.primary_page:
            pages.append(("primary", acq.primary_page))
        for p in acq.supporting_pages:
            pages.append(("supporting", p))
            
        for ptype, p in pages:
            if not p.html:
                continue
            analyzer = HtmlAnalyzer(p.html)
            signals = analyzer.analyze()
            signals.page_type = ptype
            signals.source_url = p.final_url
            signals_list.append(signals)
            
        evidence = normalize_evidence(signals_list, request.expected_language, request.expected_market)
        
        gaming_score = score_gaming_relevance(evidence)
        media_score = score_media_evidence(evidence)
        market_score, market_status = score_market_relevance(evidence, request.expected_market)
        activity_score = score_activity(evidence)
        technical_score = score_technical(evidence)
        
        component_sum = gaming_score + media_score + market_score + activity_score + technical_score
        deductions, hr_rule, hr_evidence, neg_conf = compute_deductions_and_hard_rejections(evidence)
        
        total_score = max(0, min(100, component_sum - deductions))
        
        # Apply thresholds (defaults if not in request or settings)
        verified_threshold = request.verified_threshold if getattr(request, "verified_threshold", None) is not None else getattr(self.settings, "GAMING_MEDIA_VERIFIED_THRESHOLD", 75)
        uncertain_threshold = request.uncertain_threshold if getattr(request, "uncertain_threshold", None) is not None else getattr(self.settings, "GAMING_MEDIA_UNCERTAIN_THRESHOLD", 50)
        
        # Component minimums
        gaming_min = getattr(request, "gaming_minimum", None)
        gaming_min = gaming_min if gaming_min is not None else 20
        media_min = getattr(request, "media_minimum", None)
        media_min = media_min if media_min is not None else 16
        technical_min = getattr(request, "technical_minimum", None)
        technical_min = technical_min if technical_min is not None else 4
        
        # We enforce a relevance-first logic as specified in Phase 5C
        predicted_status = "uncertain"
        relevance_label = "uncertain"
        reason = ""
        
        is_strong_negative = False
        if hr_rule:
            is_strong_negative = True
            reason = f"Hard rejection: {hr_rule}"
        elif neg_conf == "high":
            is_strong_negative = True
            reason = "High confidence negative identity."

        if is_strong_negative:
            predicted_status = "rejected"
            relevance_label = "not_gaming_media"
            if not reason:
                reason = "Strong negative identity detected."
        elif total_score >= verified_threshold:
            predicted_status = "verified"
            relevance_label = "gaming_media"
            reason = "Score meets verified threshold."
        elif total_score < uncertain_threshold:
            if technical_score >= technical_min:
                predicted_status = "rejected"
                relevance_label = "not_gaming_media"
                reason = "Score below uncertain threshold with sufficient technical footprint."
            else:
                predicted_status = "uncertain"
                relevance_label = "uncertain"
                reason = "Score below uncertain threshold, but technical footprint too low to confidently reject."
        else:
            predicted_status = "uncertain"
            relevance_label = "uncertain"
            reason = "Score in uncertain range."
            
        # Evidence Gate (Phase 5D)
        usable_primary_html = acq.primary_page is not None and acq.primary_page.html and len(acq.primary_page.html) > 0
        usable_supporting_html_count = sum(1 for p in acq.supporting_pages if p.html and len(p.html) > 0)
        valid_feed_entry_count = len([e for e in acq.feed_entries if e.title and e.url])
        
        usable_acquisition_evidence = usable_primary_html or usable_supporting_html_count > 0 or valid_feed_entry_count >= 2
        
        # Meaningful relevance evidence check
        meaningful_relevance_evidence = (
            len(evidence.gaming_navigation_terms) > 0 or
            len(evidence.gaming_article_titles) > 1 or
            len(evidence.editorial_navigation_terms) > 0 or
            len(evidence.gaming_identity_terms) > 0 or
            is_strong_negative
        )
        
        decision_override = None
        if predicted_status in ["verified", "rejected"]:
            gate_passed = False
            if predicted_status == "verified":
                if usable_acquisition_evidence and meaningful_relevance_evidence:
                    gate_passed = True
            elif predicted_status == "rejected":
                if usable_acquisition_evidence and is_strong_negative:
                    gate_passed = True
                    
            if not gate_passed:
                predicted_status = "uncertain"
                relevance_label = "uncertain"
                decision_override = "insufficient_evidence"
                reason = "Scores were calculated, but minimum evidence required for a resolved relevance decision was not available."

        return VerificationResultV2(
            requested_url=acq.primary_page.requested_url if acq.primary_page else "",
            final_url=acq.primary_page.final_url if acq.primary_page else "",
            registered_domain=acq.domain,
            classifier_version=CLASSIFIER_VERSION,
            gaming_score=gaming_score,
            media_score=media_score,
            market_score=market_score,
            activity_score=activity_score,
            technical_score=technical_score,
            component_sum=component_sum,
            contextual_deductions=deductions,
            total_score=total_score,
            hard_rejection_rule=hr_rule,
            hard_rejection_evidence=hr_evidence,
            hard_rejection_confidence=1.0 if neg_conf == "high" else 0.0,
            predicted_status=predicted_status,
            relevance_label=relevance_label,
            market_status=market_status,
            decision_reason=reason,
            decision_override=decision_override,
            evidence=evidence,
            expected_market=request.expected_market,
            expected_language=request.expected_language,
            analysed_at=datetime.now(timezone.utc),
            fetch_success=acq.usable_evidence_found,
            fetch_error_code=acq.primary_page.error_code if acq.primary_page else "unknown",
            safe_error=acq.primary_page.safe_error if acq.primary_page else "unknown"
        )
