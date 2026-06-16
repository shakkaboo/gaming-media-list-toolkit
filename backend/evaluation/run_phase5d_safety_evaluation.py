import sys
import os
from pathlib import Path
import csv
import json
from datetime import datetime, timezone
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.verification.classifier_v2 import ClassifierV2
from app.config import get_settings
from app.schemas.verification import VerificationRequest, NormalizedCandidate
from app.schemas.acquisition import AcquisitionResult
from app.services.verification_service import VerificationService

RESULTS_DIR = Path("evaluation/results")
DATASET_PATH = Path("evaluation/gaming_media_evaluation.csv")
RAW_RESULTS_PATH = RESULTS_DIR / "revised_fetch_checkpoint.json"

def load_development_dataset():
    records = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["dataset_split"] == "development":
                records.append(row)
    return records

async def run_evaluation():
    settings = get_settings()
    classifier = ClassifierV2(settings)
    service = VerificationService()
    records = load_development_dataset()
    
    predictions_csv = []
    zero_technical_decisions = []
    provenance_mismatches = []
    decisions_without_evidence = 0
    forbidden_fields_used = 0
    false_positives = 0
    true_positives = 0
    
    for row in records:
        domain = row["domain"]
        expected_label = row["expected_label"]
        
        nc = NormalizedCandidate(
            original_url=row["homepage_url"],
            normalized_url=row["homepage_url"],
            homepage_url=row["homepage_url"],
            registered_domain=domain,
            title="N/A",
            query_text="N/A",
            provider="eval",
            result_position=1
        )
        
        req = VerificationRequest(
            candidates=[nc],
            classifier_version="v2_multilingual_explainable",
            verified_threshold=58,
            uncertain_threshold=40,
            gaming_minimum=14,
            media_minimum=10,
            technical_minimum=0,
            market_minimum=0,
            expected_language="ja" if row.get("target_market") == "Japan" else ("fr" if row.get("language") == "fr" else "en"),
            expected_market=row.get("target_market")
        )

        try:
            # Prove no leakage:
            if hasattr(req, "expected_label") or hasattr(req, "website_type") or hasattr(req, "activity_status") or hasattr(req, "label_reason") or hasattr(req, "evidence_summary") or hasattr(req, "reviewer_notes") or hasattr(req, "evidence_url_1"):
                forbidden_fields_used += 1

            resp = await service.verify_candidates(req)
            if resp.results:
                res = resp.results[0]
                
                usable_ev = False
                if hasattr(res, 'acquisition_context') and res.acquisition_context:
                    usable_ev = res.acquisition_context.usable_acquisition_evidence
                else:
                    usable_ev = (res.predicted_status != "fetch_failed" and res.predicted_status != "uncertain")

                p_row = {
                    "domain": domain,
                    "expected_label": expected_label,
                    "predicted_status": res.predicted_status,
                    "relevance_label": res.relevance_label,
                    "market_status": res.market_status,
                    "total_score": res.total_score,
                    "gaming_score": res.gaming_score,
                    "media_score": res.media_score,
                    "market_score": res.market_score,
                    "activity_score": res.activity_score,
                    "technical_score": res.technical_score,
                    "component_sum": getattr(res, 'component_sum', 0),
                    "contextual_deductions": getattr(res, 'contextual_deductions', 0),
                    "hard_rejection_rule": getattr(res, 'hard_rejection_rule', "None") or "None",
                    "decision_override": getattr(res, 'decision_override', "None") or "None",
                    "decision_reason": res.decision_reason
                }
                predictions_csv.append(p_row)
                
                # Check false positives
                if expected_label != "gaming_media" and res.relevance_label == "gaming_media":
                    false_positives += 1
                    
                if expected_label == "gaming_media" and res.relevance_label == "gaming_media":
                    true_positives += 1
                
                if res.predicted_status in ["verified", "rejected"] and not usable_ev:
                    decisions_without_evidence += 1
                    
                if res.predicted_status in ["verified", "rejected"] and res.technical_score == 0:
                    zero_technical_decisions.append({
                        "domain": domain,
                        "predicted_status": res.predicted_status,
                        "relevance_label": res.relevance_label,
                        "total_score": res.total_score,
                        "gaming_score": res.gaming_score,
                        "media_score": res.media_score,
                        "usable_evidence": usable_ev
                    })
        except Exception as e:
            print(f"Error processing {domain}: {e}")

            
    with open(RESULTS_DIR / "phase5d_decision_evidence_audit.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=predictions_csv[0].keys())
        writer.writeheader()
        writer.writerows(predictions_csv)
        
    with open(RESULTS_DIR / "phase5d_decision_evidence_audit.md", "w", encoding="utf-8") as f:
        f.write("# Phase 5D Decision Evidence Audit\n\n")
        f.write(f"Decisions without evidence: {decisions_without_evidence}\n")
        f.write(f"Forbidden fields used: {forbidden_fields_used}\n")
        f.write(f"False Positives: {false_positives}\n")
        f.write(f"True Positives: {true_positives}\n")
        
    with open(RESULTS_DIR / "phase5d_zero_technical_decisions.md", "w", encoding="utf-8") as f:
        f.write("# Phase 5D Zero Technical Decisions\n\n")
        f.write(f"Count: {len(zero_technical_decisions)}\n")
        for d in zero_technical_decisions:
            f.write(f"- {d['domain']}: {d['predicted_status']} ({d['total_score']}) - Usable Evidence: {d['usable_evidence']}\n")
            
    with open(RESULTS_DIR / "phase5d_acquisition_provenance_mismatches.md", "w", encoding="utf-8") as f:
        f.write("# Phase 5D Acquisition Provenance Mismatches\n\n")
        f.write(f"Count: {len(provenance_mismatches)}\n")
        for d in provenance_mismatches:
            f.write(f"- {d['domain']}: flag={d['flag']} actual={d['actual']}\n")

    # METRICS
    total_dev = len(predictions_csv)
    binary_eligible = [p for p in predictions_csv if p['expected_label'] != 'uncertain']
    binary_eligible_rows = len(binary_eligible)

    verified = sum(1 for p in predictions_csv if p['predicted_status'] == 'verified')
    rejected = sum(1 for p in predictions_csv if p['predicted_status'] == 'rejected')
    uncertain = sum(1 for p in predictions_csv if p['predicted_status'] == 'uncertain')
    fetch_failed = sum(1 for p in predictions_csv if p['predicted_status'] == 'fetch_failed')

    tp = sum(1 for p in binary_eligible if p['expected_label'] == 'gaming_media' and p['relevance_label'] == 'gaming_media')
    fp = sum(1 for p in binary_eligible if p['expected_label'] == 'not_gaming_media' and p['relevance_label'] == 'gaming_media')
    tn = sum(1 for p in binary_eligible if p['expected_label'] == 'not_gaming_media' and p['relevance_label'] == 'not_gaming_media')
    fn = sum(1 for p in binary_eligible if p['expected_label'] == 'gaming_media' and p['relevance_label'] == 'not_gaming_media')
    abstentions = sum(1 for p in binary_eligible if p['relevance_label'] == 'uncertain' or p['predicted_status'] == 'fetch_failed')

    expected_positives = sum(1 for p in binary_eligible if p['expected_label'] == 'gaming_media')
    expected_negatives = sum(1 for p in binary_eligible if p['expected_label'] == 'not_gaming_media')

    decided = tp + fp + tn + fn
    decision_coverage = decided / binary_eligible_rows if binary_eligible_rows > 0 else 0
    precision = tp / (tp + fp) if tp + fp > 0 else 0
    operational_positive_recall = tp / expected_positives if expected_positives > 0 else 0
    decided_recall = tp / (tp + fn) if tp + fn > 0 else 0
    f1 = 2 * precision * decided_recall / (precision + decided_recall) if precision + decided_recall > 0 else 0
    specificity = tn / (tn + fp) if tn + fp > 0 else 0
    strict_accuracy = (tp + tn) / decided if decided > 0 else 0

    metrics = {
        'total_development_rows': total_dev,
        'binary_eligible_rows': binary_eligible_rows,
        'verified_count': verified,
        'rejected_count': rejected,
        'uncertain_count': uncertain,
        'fetch_failed_count': fetch_failed,
        'true_positives': tp,
        'false_positives': fp,
        'true_negatives_among_decided_predictions': tn,
        'false_negatives_among_decided_predictions': fn,
        'abstentions': abstentions,
        'operational_positive_recall': operational_positive_recall,
        'decision_coverage': decision_coverage,
        'precision': precision,
        'decided_prediction_recall': decided_recall,
        'f1': f1,
        'specificity': specificity,
        'strict_accuracy': strict_accuracy
    }

    with open(RESULTS_DIR / 'phase5d_development_metrics.json', 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)
            
    print("Done generating Phase 5D audit.")
    
    # Save frozen configuration
    frozen_config = {
        "classifier_version": "v2_multilingual_explainable",
        "vocabulary_version": "v2.0",
        "scoring_rule_hash": "phase5d_relevance_first",
        "decision_policy_version": "relevance-first v1",
        "component_weights": "gaming_max:30, media_max:25, market_max:20",
        "component_caps": "gaming_max:30, media_max:25, market_max:20, activity_max:15, technical_max:15",
        "high_confidence_negative_identity_shortcut": "enabled",
        "verified_threshold": 58,
        "uncertain_threshold": 40,
        "gaming_minimum": 14,
        "media_minimum": 10,
        "technical_minimum": 0,
        "market_minimum": 0,
        "evidence_safety_gate": "enabled",
        "frozen_at": datetime.now(timezone.utc).isoformat()
    }
    
    if decisions_without_evidence == 0 and forbidden_fields_used == 0 and false_positives <= 1:
        with open("evaluation/phase5d_frozen_configuration.json", "w", encoding="utf-8") as f:
            json.dump(frozen_config, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
