from datetime import datetime, timezone
from typing import Optional
from app.schemas.verification import ExtractedSiteSignals, VerificationResult, VerificationReason
from app.config import get_settings
from app.verification.rules import (
    evaluate_gaming_relevance,
    evaluate_editorial_structure,
    evaluate_activity,
    evaluate_publication_identity,
    evaluate_negative_penalties,
    detect_categories
)

CLASSIFIER_VERSION = "rule_based_v1"

class Classifier:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def classify(self, 
                 requested_url: str, 
                 final_url: str, 
                 registered_domain: str, 
                 signals: ExtractedSiteSignals,
                 current_time: datetime = None,
                 verified_threshold_override: Optional[int] = None,
                 uncertain_threshold_override: Optional[int] = None) -> VerificationResult:
        if current_time is None:
            current_time = datetime.now(timezone.utc)
            
        gaming_score, gaming_reasons = evaluate_gaming_relevance(signals)
        editorial_score, editorial_reasons = evaluate_editorial_structure(signals)
        activity_score, activity_status, newest_date, activity_reasons = evaluate_activity(signals, current_time)
        identity_score, identity_reasons = evaluate_publication_identity(signals)
        negative_penalty, negative_reasons = evaluate_negative_penalties(signals)
        
        categories = detect_categories(signals)
        
        raw_score = gaming_score + editorial_score + activity_score + identity_score - negative_penalty
        score = max(0, min(100, raw_score))
        
        status = "rejected"
        confidence = 0.5
        
        if "cloudflare_challenge" in signals.challenge_indicators or "access_denied" in signals.challenge_indicators:
            status = "uncertain"
            confidence = 0.1
            negative_reasons.append(VerificationReason(code="challenge_page", message="Challenge or access denied page detected", weight=-100, evidence=signals.challenge_indicators))
            score = 0
            
        elif "domain_parked_or_for_sale" in signals.parking_indicators:
            status = "rejected"
            confidence = 0.9
            negative_reasons.append(VerificationReason(code="parked_domain", message="Domain is parked or for sale", weight=-100, evidence=signals.parking_indicators))
            score = 0
            
        else:
            v_thresh = verified_threshold_override if verified_threshold_override is not None else self.settings.GAMING_MEDIA_VERIFIED_THRESHOLD
            u_thresh = uncertain_threshold_override if uncertain_threshold_override is not None else self.settings.GAMING_MEDIA_UNCERTAIN_THRESHOLD
            
            if score >= v_thresh:
                if gaming_score >= 18 and editorial_score >= 18:
                    status = "verified"
                else:
                    status = "uncertain"
                    negative_reasons.append(VerificationReason(code="missing_minimum_subscores", message="Score is high but minimum gaming or editorial evidence is missing", weight=0, evidence=[]))
            elif score >= u_thresh:
                status = "uncertain"
            else:
                status = "rejected"
                
            # Confidence logic
            total_positive_evidence = len(gaming_reasons) + len(editorial_reasons) + len(activity_reasons) + len(identity_reasons)
            evidence_cov = min(0.40, total_positive_evidence * 0.05)
            
            agreement = 0.0
            if gaming_score >= 15 and editorial_score >= 15:
                agreement = 0.20
                
            struct_data = 0.0
            if len(signals.json_ld_types) > 0:
                struct_data = 0.15
                
            act_conf = 0.0
            if activity_status in ["active_recently", "possibly_active"]:
                act_conf = 0.15
                
            comp = 0.10 if (signals.page_title and signals.headings) else 0.0
            
            conflict = 0.0
            if negative_penalty > 20 and score > 40:
                conflict = -0.30
                
            raw_conf = evidence_cov + agreement + struct_data + act_conf + comp + conflict
            confidence = max(0.0, min(1.0, raw_conf))
            
            if negative_penalty >= 40 and editorial_score < 18:
                status = "rejected"
                confidence = max(confidence, 0.8)
                negative_reasons.append(VerificationReason(code="forced_rejection", message="Strong negative signals with insufficient editorial structure", weight=0, evidence=[]))
        
        # Determine language/market matching logic (basic stub as requested)
        market_evidence = []
        if signals.html_language:
            market_evidence.append(f"lang={signals.html_language}")
            
        return VerificationResult(
            requested_url=requested_url,
            final_url=final_url,
            registered_domain=registered_domain,
            score=score,
            verification_status=status,
            confidence=round(confidence, 2),
            gaming_relevance_score=gaming_score,
            editorial_structure_score=editorial_score,
            activity_score=activity_score,
            publication_identity_score=identity_score,
            negative_penalty=negative_penalty,
            positive_reasons=gaming_reasons + editorial_reasons + activity_reasons + identity_reasons,
            negative_reasons=negative_reasons,
            detected_categories=categories,
            activity_status=activity_status,
            newest_detected_publication_date=newest_date,
            article_count_estimate=len(signals.article_links),
            classifier_version=CLASSIFIER_VERSION,
            analysed_at=datetime.now(timezone.utc),
            fetch_success=True,
            detected_language=signals.html_language,
            market_evidence=market_evidence
        )
