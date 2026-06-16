import asyncio
import csv
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

from app.services.verification_service import VerificationService
from app.schemas.verification import VerificationRequest
from app.schemas.search import NormalizedCandidate
from app.verification.rules_v2 import get_vocabulary_hash

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RESULTS_DIR = Path("evaluation/results")
DATASET_PATH = Path("evaluation/gaming_media_evaluation.csv")
CHECKPOINT_PATH = RESULTS_DIR / "phase5c_checkpoint.json"

def load_development_dataset():
    records = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["dataset_split"] == "development":
                records.append(row)
    
    for r in records:
        if r["dataset_split"] == "test":
            raise ValueError("Test row found in Phase 5C development evaluation")
            
    return records

async def run_evaluation(resume: bool):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    records = load_development_dataset()
    logger.info(f"Loaded {len(records)} development records.")
    
    service = VerificationService()
    
    checkpoint_data = {}
    if resume and CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            checkpoint_data = json.load(f)
        logger.info(f"Resumed from checkpoint, {len(checkpoint_data)} records already processed.")
    elif not resume:
        if CHECKPOINT_PATH.exists():
            CHECKPOINT_PATH.unlink()
    
    for r in records:
        domain = r["domain"]
        if domain in checkpoint_data:
            continue
            
        nc = NormalizedCandidate(
            original_url=r["homepage_url"],
            normalized_url=r["homepage_url"],
            homepage_url=r["homepage_url"],
            registered_domain=domain,
            title="N/A",
            query_text="N/A",
            provider="eval",
            result_position=1
        )
        req = VerificationRequest(
            candidates=[nc],
            classifier_version="v2_multilingual_explainable",
            verified_threshold=0,
            uncertain_threshold=0,
            gaming_minimum=0,
            media_minimum=0,
            market_minimum=0,
            technical_minimum=0,
            expected_language="ja" if r.get("target_market") == "Japan" else ("fr" if r.get("language") == "fr" else "en"),
            expected_market=r.get("target_market")
        )
        try:
            resp = await service.verify_candidates(req)
            if resp.results:
                res = resp.results[0]
                # Serialize result to dict
                res_dict = {
                    "registered_domain": res.registered_domain,
                    "gaming_score": res.gaming_score,
                    "media_score": res.media_score,
                    "market_score": res.market_score,
                    "activity_score": res.activity_score,
                    "technical_score": res.technical_score,
                    "component_sum": res.component_sum,
                    "contextual_deductions": res.contextual_deductions,
                    "total_score": res.total_score,
                    "hard_rejection_rule": res.hard_rejection_rule,
                    "hard_rejection_confidence": res.hard_rejection_confidence,
                    "predicted_status": res.predicted_status,
                    "relevance_label": res.relevance_label,
                    "market_status": res.market_status,
                    "decision_reason": res.decision_reason
                }
                checkpoint_data[domain] = res_dict
                
                # Checkpoint after each domain
                with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
                    json.dump(checkpoint_data, f)
        except Exception as e:
            logger.error(f"Error evaluating {domain}: {e}")
            
    v2_results = list(checkpoint_data.values())
    
    thresholds_to_test = [
        {"id": 1, "purpose": "Baseline from 5B", "high_conf_neg": False, "verified_threshold": 60, "uncertain_threshold": 40, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 2, "market_minimum": 0},
        {"id": 2, "purpose": "Enable high-conf neg", "high_conf_neg": True, "verified_threshold": 60, "uncertain_threshold": 40, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 2, "market_minimum": 0},
        {"id": 3, "purpose": "Tech min 0", "high_conf_neg": True, "verified_threshold": 60, "uncertain_threshold": 40, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 0, "market_minimum": 0},
        {"id": 4, "purpose": "Tech min 0, higher verified", "high_conf_neg": True, "verified_threshold": 62, "uncertain_threshold": 40, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 0, "market_minimum": 0},
        {"id": 5, "purpose": "Tech min 0, lower verified", "high_conf_neg": True, "verified_threshold": 58, "uncertain_threshold": 40, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 0, "market_minimum": 0},
        {"id": 6, "purpose": "Higher technical min", "high_conf_neg": True, "verified_threshold": 60, "uncertain_threshold": 40, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 3, "market_minimum": 0},
        {"id": 7, "purpose": "Lower verified", "high_conf_neg": True, "verified_threshold": 58, "uncertain_threshold": 40, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 2, "market_minimum": 0},
        {"id": 8, "purpose": "Lower uncertain", "high_conf_neg": True, "verified_threshold": 60, "uncertain_threshold": 38, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 2, "market_minimum": 0},
        {"id": 9, "purpose": "Higher verified, lower uncertain", "high_conf_neg": True, "verified_threshold": 62, "uncertain_threshold": 38, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 2, "market_minimum": 0},
        {"id": 10, "purpose": "Tech min 0, lower uncertain", "high_conf_neg": True, "verified_threshold": 60, "uncertain_threshold": 38, "gaming_minimum": 14, "media_minimum": 10, "technical_minimum": 0, "market_minimum": 0},
    ]
                        
    logger.info(f"Evaluating {len(thresholds_to_test)} threshold candidates offline.")
    
    def evaluate_threshold(t: Dict[str, Any]) -> Dict[str, Any]:
        tp, fp, fn_decided, tn_decided, abstentions = 0, 0, 0, 0, 0
        total_eligible = 0
        total_expected_pos = 0
        
        for res in v2_results:
            domain = res["registered_domain"]
            expected_row = next(r for r in records if r["domain"] == domain)
            expected = expected_row["expected_label"]
            
            if expected == "gaming_media":
                total_expected_pos += 1
                total_eligible += 1
            elif expected == "not_gaming_media":
                total_eligible += 1
            
            hr_rule = res["hard_rejection_rule"]
            total_score = res["total_score"]
            gaming_score = res["gaming_score"]
            media_score = res["media_score"]
            technical_score = res["technical_score"]
            neg_conf_score = res.get("hard_rejection_confidence", 0.0)
            
            is_strong_negative = False
            if hr_rule and hr_rule != "high_confidence_negative_identity":
                is_strong_negative = True
            elif t["high_conf_neg"] and neg_conf_score == 1.0 and gaming_score <= 20 and media_score <= 15:
                is_strong_negative = True
                
            predicted_status = "uncertain"
            if is_strong_negative:
                predicted_status = "rejected"
            elif total_score >= t["verified_threshold"] and gaming_score >= t["gaming_minimum"] and media_score >= t["media_minimum"] and technical_score >= t["technical_minimum"]:
                predicted_status = "verified"
            elif total_score < t["uncertain_threshold"] and technical_score >= t["technical_minimum"]:
                predicted_status = "rejected"
            else:
                predicted_status = "uncertain"
                
            # Exclude expected uncertain rows from binary evaluation metrics (except as total count)
            if expected == "uncertain":
                continue
                
            if predicted_status == "uncertain" or predicted_status == "fetch_failed":
                abstentions += 1
            elif predicted_status == "verified":
                if expected == "gaming_media":
                    tp += 1
                else:
                    fp += 1
            elif predicted_status == "rejected":
                if expected == "not_gaming_media":
                    tn_decided += 1
                else:
                    fn_decided += 1
            
        decided_eligible = tp + fp + tn_decided + fn_decided
        coverage = decided_eligible / total_eligible if total_eligible > 0 else 0
        operational_recall = tp / total_expected_pos if total_expected_pos > 0 else 0
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall_decided = tp / (tp + fn_decided) if (tp + fn_decided) > 0 else 0
        f1 = 2 * precision * recall_decided / (precision + recall_decided) if (precision + recall_decided) > 0 else 0
        specificity = tn_decided / (tn_decided + fp) if (tn_decided + fp) > 0 else 0
        
        accuracy = (tp + tn_decided) / total_eligible if total_eligible > 0 else 0
        
        return {
            "thresholds": t,
            "metrics": {
                "tp": tp, "fp": fp, "fn_decided": fn_decided, "tn_decided": tn_decided, "abstentions": abstentions,
                "precision": precision, "decided_recall": recall_decided, "operational_recall": operational_recall, 
                "f1": f1, "coverage": coverage, "strict_accuracy": accuracy, "specificity": specificity
            }
        }
        
    eval_results = [evaluate_threshold(t) for t in thresholds_to_test]
    
    def sort_key(cr):
        m = cr["metrics"]
        t = cr["thresholds"]
        
        # 1. False positives must be <= 1.
        meets_rule1 = 1 if m["fp"] <= 1 else 0
        
        # 2. Operational positive recall must be >= 50%.
        meets_rule2 = 1 if m["operational_recall"] >= 0.50 else 0
        
        # 3. Decision coverage must be >= 60%.
        meets_rule3 = 1 if m["coverage"] >= 0.60 else 0
        
        # 4. Among qualifying configurations, prefer the fewest false positives.
        fp_score = -m["fp"]
        
        # 5. Then choose the highest operational positive recall.
        recall_score = m["operational_recall"]
        
        # 6. Then choose the highest coverage.
        coverage_score = m["coverage"]
        
        # 7. Then choose the highest F1.
        f1_score = m["f1"]
        
        # 8. Prefer the simpler configuration when effectively tied.
        simplicity = -(t["verified_threshold"] + t["gaming_minimum"] + t["media_minimum"] + t["technical_minimum"])
        
        return (
            meets_rule1,
            meets_rule2,
            meets_rule3,
            fp_score,
            recall_score,
            coverage_score,
            f1_score,
            simplicity
        )
        
    best_candidate = max(eval_results, key=sort_key)
    
    with open(RESULTS_DIR / "phase5c_configuration_comparison.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Purpose", "HighConfNeg", "VT", "UT", "GM", "MM", "TM", "Precision", "Decided_Recall", "Operational_Recall", "F1", "FP", "FN_Decided", "Abstentions", "Coverage"])
        for cr in sorted(eval_results, key=sort_key, reverse=True):
            t = cr["thresholds"]
            m = cr["metrics"]
            writer.writerow([t["id"], t["purpose"], t["high_conf_neg"], t["verified_threshold"], t["uncertain_threshold"], t["gaming_minimum"], t["media_minimum"], t["technical_minimum"],
                             f"{m['precision']:.3f}", f"{m['decided_recall']:.3f}", f"{m['operational_recall']:.3f}", f"{m['f1']:.3f}", m['fp'], m['fn_decided'], m['abstentions'], f"{m['coverage']:.3f}"])
                             
    t_best = best_candidate["thresholds"]
    best_metrics = best_candidate["metrics"]
    
    predictions_csv = []
    for res in v2_results:
        domain = res["registered_domain"]
        expected = next(r["expected_label"] for r in records if r["domain"] == domain)
        
        hr_rule = res["hard_rejection_rule"]
        total_score = res["total_score"]
        gaming_score = res["gaming_score"]
        media_score = res["media_score"]
        market_score = res["market_score"]
        technical_score = res["technical_score"]
        neg_conf_score = res.get("hard_rejection_confidence", 0.0)
        
        is_strong_negative = False
        if hr_rule and hr_rule != "high_confidence_negative_identity":
            is_strong_negative = True
        elif t_best["high_conf_neg"] and neg_conf_score == 1.0 and gaming_score <= 20 and media_score <= 15:
            is_strong_negative = True
            hr_rule = "high_confidence_negative_identity"
            
        predicted_status = "uncertain"
        reason = ""
        if is_strong_negative:
            predicted_status = "rejected"
            reason = f"Hard rejection: {hr_rule}"
        elif total_score >= t_best["verified_threshold"] and gaming_score >= t_best["gaming_minimum"] and media_score >= t_best["media_minimum"] and technical_score >= t_best["technical_minimum"]:
            predicted_status = "verified"
            reason = "Met all component minimums and verified threshold."
        elif total_score < t_best["uncertain_threshold"] and technical_score >= t_best["technical_minimum"]:
            predicted_status = "rejected"
            reason = "Total score below uncertain threshold."
        else:
            predicted_status = "uncertain"
            if technical_score < t_best["technical_minimum"]:
                reason = "Low total score, but technical confidence too low for rejection."
            else:
                reason = "Score in uncertain range, incomplete or conflicting evidence."
                
        relevance_label = "uncertain"
        if is_strong_negative:
            relevance_label = "not_gaming_media"
        elif total_score >= t_best["verified_threshold"] and gaming_score >= t_best["gaming_minimum"] and media_score >= t_best["media_minimum"] and technical_score >= t_best["technical_minimum"]:
            relevance_label = "gaming_media"
        elif total_score < t_best["uncertain_threshold"] and technical_score >= t_best["technical_minimum"]:
            relevance_label = "not_gaming_media"
                
        predictions_csv.append({
            "domain": domain,
            "expected_label": expected,
            "predicted_status": predicted_status,
            "relevance_label": relevance_label,
            "market_status": res["market_status"],
            "total_score": total_score,
            "gaming_score": gaming_score,
            "media_score": media_score,
            "market_score": market_score,
            "activity_score": res["activity_score"],
            "technical_score": technical_score,
            "contextual_deductions": res["contextual_deductions"],
            "hard_rejection_rule": hr_rule,
            "decision_reason": reason
        })
        
    with open(RESULTS_DIR / "phase5c_development_predictions.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=predictions_csv[0].keys())
        writer.writeheader()
        writer.writerows(predictions_csv)
        
    with open(RESULTS_DIR / "phase5c_development_metrics.json", "w", encoding="utf-8") as f:
        json.dump(best_metrics, f, indent=2)
        
    vocab_hash = get_vocabulary_hash()
    config_hash_input = f"{vocab_hash}-{t_best['verified_threshold']}-{t_best['uncertain_threshold']}-{t_best['gaming_minimum']}-{t_best['media_minimum']}-{t_best['market_minimum']}-{t_best['technical_minimum']}-{t_best['high_conf_neg']}"
    import hashlib
    config_hash = hashlib.sha256(config_hash_input.encode('utf-8')).hexdigest()[:8]
    
    frozen_config = {
        "classifier_version": "v2_multilingual_explainable",
        "vocabulary_version": "v2.0",
        "vocabulary_hash": vocab_hash,
        "scoring_rule_hash": "phase5c_relevance_first",
        "decision_policy_version": "relevance-first v1",
        "component_weights": "gaming_max:30, media_max:25, market_max:20",
        "component_caps": "gaming_max:30, media_max:25, market_max:20, activity_max:15, technical_max:15",
        "deduction_values_and_caps": "store max 20, dev max 20, casino max 30, hw max 15. Combined cap: 35",
        "hard_rejection_definitions": ["dominant_ecommerce_store", "game_developer_corporate_site", "casino_or_betting_site", "hardware_manufacturer"],
        "high_confidence_negative_identity_rules": {
            "enabled": t_best["high_conf_neg"],
            "max_gaming_score": 20,
            "max_media_score": 15
        },
        "verified_threshold": t_best["verified_threshold"],
        "uncertain_threshold": t_best["uncertain_threshold"],
        "component_minimums": {
            "gaming": t_best["gaming_minimum"],
            "media": t_best["media_minimum"],
            "market": t_best["market_minimum"],
            "technical": t_best["technical_minimum"]
        },
        "relevance_market_separation_policy": "Relevance verified even if market unconfirmed.",
        "selection_policy": "1. FP<=1 2. OpRecall>=50% 3. Cov>=60% 4. Min FP 5. Max OpRecall 6. Max Cov 7. Max F1 8. Simplicity",
        "development_metrics": best_metrics,
        "configuration_hash": config_hash,
        "frozen_at": datetime.now(timezone.utc).isoformat()
    }
    
    with open("evaluation/phase5c_frozen_configuration.json", "w", encoding="utf-8") as f:
        json.dump(frozen_config, f, indent=2)
        
    with open(RESULTS_DIR / "phase5c_configuration_selection.md", "w", encoding="utf-8") as f:
        f.write("# Phase 5C Configuration Selection\n\n")
        f.write(f"Evaluated {len(eval_results)} candidates.\n\n")
        f.write(f"Selected: {t_best}\n\n")
        f.write(f"Metrics: {best_metrics}\n\n")
        
    with open(RESULTS_DIR / "phase5c_error_analysis.md", "w", encoding="utf-8") as f:
        f.write("# Phase 5C Development Error Analysis\n\n")
        for p in predictions_csv:
            is_fp = (p["expected_label"] != "gaming_media" and p["relevance_label"] == "gaming_media")
            is_fn = (p["expected_label"] == "gaming_media" and p["relevance_label"] != "gaming_media" and p["relevance_label"] != "uncertain")
            is_abstention_fn = (p["expected_label"] == "gaming_media" and p["relevance_label"] == "uncertain")
            if is_fp or is_fn or is_abstention_fn:
                f.write(f"## {p['domain']} ({p['expected_label']} -> predicted: {p['predicted_status']}, relevance: {p['relevance_label']})\n")
                f.write(f"* Scores: Total: {p['total_score']} (G:{p['gaming_score']} M:{p['media_score']} Mk:{p['market_score']} A:{p['activity_score']} T:{p['technical_score']})\n")
                f.write(f"* Deductions: {p['contextual_deductions']} HR: {p['hard_rejection_rule']}\n")
                f.write(f"* Reason: {p['decision_reason']}\n\n")

if __name__ == "__main__":
    resume = "--resume" in sys.argv
    asyncio.run(run_evaluation(resume))
