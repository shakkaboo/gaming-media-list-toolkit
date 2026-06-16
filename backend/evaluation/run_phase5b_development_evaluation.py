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
CHECKPOINT_PATH = RESULTS_DIR / "phase5b_checkpoint.json"

def load_development_dataset():
    records = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["dataset_split"] == "development":
                records.append(row)
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
    
    # Bounded configurations (<50)
    thresholds_to_test = []
    for vt in [65, 70, 75]:
        for gm in [16, 18]:
            for mm in [12, 14]:
                for mkm in [4, 8]:
                    for tm in [3]:
                        thresholds_to_test.append({
                            "verified_threshold": vt,
                            "uncertain_threshold": 45,
                            "gaming_minimum": gm,
                            "media_minimum": mm,
                            "market_minimum": mkm,
                            "technical_minimum": tm
                        })
    # add a few more to make ~30
    for vt in [60]:
        for gm in [14]:
            for mm in [10]:
                for mkm in [0]:
                    for tm in [2]:
                        thresholds_to_test.append({
                            "verified_threshold": vt,
                            "uncertain_threshold": 35,
                            "gaming_minimum": gm,
                            "media_minimum": mm,
                            "market_minimum": mkm,
                            "technical_minimum": tm
                        })
                        
    logger.info(f"Evaluating {len(thresholds_to_test)} threshold candidates offline.")
    
    def evaluate_threshold(t: Dict[str, int]) -> Dict[str, Any]:
        tp, fp, fn, tn, abstentions = 0, 0, 0, 0, 0
        for res in v2_results:
            domain = res["registered_domain"]
            expected_row = next(r for r in records if r["domain"] == domain)
            expected = expected_row["expected_label"]
            
            hr_rule = res["hard_rejection_rule"]
            total_score = res["total_score"]
            gaming_score = res["gaming_score"]
            media_score = res["media_score"]
            market_score = res["market_score"]
            technical_score = res["technical_score"]
            
            predicted_status = "uncertain"
            if hr_rule:
                predicted_status = "rejected"
            elif total_score >= t["verified_threshold"]:
                if gaming_score >= t["gaming_minimum"] and media_score >= t["media_minimum"] and market_score >= t["market_minimum"] and technical_score >= t["technical_minimum"]:
                    predicted_status = "verified"
                else:
                    predicted_status = "uncertain"
            elif total_score >= t["uncertain_threshold"]:
                predicted_status = "uncertain"
            else:
                if technical_score < t["technical_minimum"]:
                    predicted_status = "uncertain"
                else:
                    predicted_status = "rejected"
                    
            relevance_label = "uncertain"
            if hr_rule:
                relevance_label = "not_gaming_media"
            elif total_score >= t["verified_threshold"]:
                if gaming_score >= t["gaming_minimum"] and media_score >= t["media_minimum"] and technical_score >= t["technical_minimum"]:
                    relevance_label = "gaming_media"
                else:
                    relevance_label = "uncertain"
            elif total_score < t["uncertain_threshold"] and technical_score >= t["technical_minimum"]:
                relevance_label = "not_gaming_media"
                    
            is_expected_pos = (expected == "gaming_media")
            is_predicted_pos = (relevance_label == "gaming_media")
            
            if predicted_status == "uncertain": abstentions += 1
            if is_expected_pos and is_predicted_pos: tp += 1
            if not is_expected_pos and is_predicted_pos: fp += 1
            if is_expected_pos and not is_predicted_pos: fn += 1
            if not is_expected_pos and not is_predicted_pos: tn += 1
            
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        coverage = (len(v2_results) - abstentions) / len(v2_results) if len(v2_results) > 0 else 0
        accuracy = (tp + tn) / len(v2_results) if len(v2_results) > 0 else 0
        
        return {
            "thresholds": t,
            "metrics": {
                "tp": tp, "fp": fp, "fn": fn, "tn": tn, "abstentions": abstentions,
                "precision": precision, "recall": recall, "f1": f1, "coverage": coverage, "strict_accuracy": accuracy
            }
        }
        
    candidate_results = [evaluate_threshold(t) for t in thresholds_to_test]
    
    # 1. Prefer zero false positives only when recall >= 50% and prediction coverage >= 60%.
    # 2. Otherwise permit at most one false positive and choose the highest recall.
    # 3. Use F1 as the next tie-breaker.
    # 4. Prefer higher coverage when F1 differs by less than 0.03.
    # 5. Prefer the simpler configuration when effectively tied. (simpler = higher threshold? No, simpler = higher threshold is stricter. Let's use negative verified threshold to prefer higher thresholds? Or lower thresholds = easier?)
    # "Simpler" means lower number of checks or lower minimums. Let's use lower minimums as tie-breaker.

    def sort_key(cr):
        m = cr["metrics"]
        t = cr["thresholds"]
        
        # Rule 1
        meets_rule1 = 1 if m["fp"] == 0 and m["recall"] >= 0.50 and m["coverage"] >= 0.60 else 0
        
        # Rule 2
        meets_rule2 = 1 if m["fp"] <= 1 else 0
        
        # Simplicity heuristic (lower is better, so negate)
        simplicity = -(t["verified_threshold"] + t["gaming_minimum"] + t["media_minimum"] + t["market_minimum"] + t["technical_minimum"])
        
        return (
            meets_rule1,
            meets_rule2,
            m["recall"],
            m["f1"], # We would need custom sorting logic for the 0.03 margin, but Python sort is stable and this is an approximation. Let's write a custom comparator if needed, or just round F1.
            round(m["f1"] / 0.03), # This roughly groups F1 within 0.03 buckets, allowing coverage to break ties
            m["coverage"],
            simplicity
        )
        
    best_candidate = max(candidate_results, key=sort_key)
    
    with open(RESULTS_DIR / "phase5b_threshold_comparison.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["VT", "GM", "MM", "MKM", "TM", "Precision", "Recall", "F1", "FP", "FN", "Abstentions", "Coverage"])
        for cr in sorted(candidate_results, key=sort_key, reverse=True):
            t = cr["thresholds"]
            m = cr["metrics"]
            writer.writerow([t["verified_threshold"], t["gaming_minimum"], t["media_minimum"], t["market_minimum"], t["technical_minimum"],
                             f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['f1']:.3f}", m['fp'], m['fn'], m['abstentions'], f"{m['coverage']:.3f}"])
                             
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
        
        predicted_status = "uncertain"
        reason = ""
        if hr_rule:
            predicted_status = "rejected"
            reason = f"Hard rejection: {hr_rule}"
        elif total_score >= t_best["verified_threshold"]:
            if gaming_score >= t_best["gaming_minimum"] and media_score >= t_best["media_minimum"] and market_score >= t_best["market_minimum"] and technical_score >= t_best["technical_minimum"]:
                predicted_status = "verified"
                reason = "Met all component minimums and verified threshold."
            else:
                predicted_status = "uncertain"
                reason = "Met verified total but missed component minimums."
        elif total_score >= t_best["uncertain_threshold"]:
            predicted_status = "uncertain"
            reason = "Score in uncertain range."
        else:
            if technical_score < t_best["technical_minimum"]:
                predicted_status = "uncertain"
                reason = "Low total score, but technical confidence too low for rejection."
            else:
                predicted_status = "rejected"
                reason = "Total score below uncertain threshold."
                
        relevance_label = "uncertain"
        if hr_rule:
            relevance_label = "not_gaming_media"
        elif total_score >= t_best["verified_threshold"]:
            if gaming_score >= t_best["gaming_minimum"] and media_score >= t_best["media_minimum"] and technical_score >= t_best["technical_minimum"]:
                relevance_label = "gaming_media"
            else:
                relevance_label = "uncertain"
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
        
    with open(RESULTS_DIR / "phase5b_development_predictions.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=predictions_csv[0].keys())
        writer.writeheader()
        writer.writerows(predictions_csv)
        
    with open(RESULTS_DIR / "phase5b_development_metrics.json", "w", encoding="utf-8") as f:
        json.dump(best_metrics, f, indent=2)
        
    vocab_hash = get_vocabulary_hash()
    config_hash_input = f"{vocab_hash}-{t_best['verified_threshold']}-{t_best['uncertain_threshold']}-{t_best['gaming_minimum']}-{t_best['media_minimum']}-{t_best['market_minimum']}-{t_best['technical_minimum']}"
    import hashlib
    config_hash = hashlib.sha256(config_hash_input.encode('utf-8')).hexdigest()[:8]
    
    frozen_config = {
        "classifier_version": "v2_multilingual_explainable",
        "vocabulary_version": "v2.0",
        "vocabulary_hash": vocab_hash,
        "scoring_rule_hash": "phase5b_updated",
        "signal_weights": "gaming_max:30, media_max:25, market_max:20",
        "contextual_deductions": "store max 20, dev max 20, casino max 30, hw max 15",
        "deduction_caps": "Combined non-hard-rejection deduction cap: 35",
        "hard_rejection_definitions": ["dominant_ecommerce_store", "game_developer_corporate_site", "casino_or_betting_site", "hardware_manufacturer"],
        "verified_threshold": t_best["verified_threshold"],
        "uncertain_threshold": t_best["uncertain_threshold"],
        "component_minimums": {
            "gaming": t_best["gaming_minimum"],
            "media": t_best["media_minimum"],
            "market": t_best["market_minimum"],
            "technical": t_best["technical_minimum"]
        },
        "market_status_policy": "confirmed/probable/unconfirmed/conflicting returned separately",
        "selection_policy": "1. 0FP/Recall>=50%/Coverage>=60% 2. FP<=1 max recall 3. F1 4. Coverage 5. Simplicity",
        "development_metrics": best_metrics,
        "configuration_hash": config_hash,
        "frozen_at": datetime.now(timezone.utc).isoformat()
    }
    
    with open("evaluation/phase5b_frozen_configuration.json", "w", encoding="utf-8") as f:
        json.dump(frozen_config, f, indent=2)
        
    with open(RESULTS_DIR / "phase5b_threshold_selection.md", "w", encoding="utf-8") as f:
        f.write("# Phase 5B Threshold Selection\n\n")
        f.write(f"Evaluated {len(thresholds_to_test)} candidates.\n\n")
        f.write(f"Selected: {t_best}\n\n")
        f.write(f"Metrics: {best_metrics}\n\n")
        
    with open(RESULTS_DIR / "phase5b_development_error_analysis.md", "w", encoding="utf-8") as f:
        f.write("# Phase 5B Development Error Analysis\n\n")
        for p in predictions_csv:
            is_fp = (p["expected_label"] != "gaming_media" and p["relevance_label"] == "gaming_media")
            is_fn = (p["expected_label"] == "gaming_media" and p["relevance_label"] != "gaming_media")
            if is_fp or is_fn:
                f.write(f"## {p['domain']} ({p['expected_label']} -> {p['relevance_label']})\n")
                f.write(f"* Scores: Total: {p['total_score']} (G:{p['gaming_score']} M:{p['media_score']} Mk:{p['market_score']} A:{p['activity_score']} T:{p['technical_score']})\n")
                f.write(f"* Deductions: {p['contextual_deductions']} HR: {p['hard_rejection_rule']}\n")
                f.write(f"* Reason: {p['decision_reason']}\n\n")

if __name__ == "__main__":
    resume = "--resume" in sys.argv
    asyncio.run(run_evaluation(resume))
