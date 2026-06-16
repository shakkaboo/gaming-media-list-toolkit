import asyncio
import csv
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

from app.services.verification_service import VerificationService
from app.schemas.verification import VerificationRequest
from app.schemas.search import NormalizedCandidate
from app.verification.rules_v2 import get_vocabulary_hash

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RESULTS_DIR = Path("backend/evaluation/results")
DATASET_PATH = Path("backend/evaluation/gaming_media_evaluation.csv")

def load_development_dataset():
    records = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["dataset_split"] == "development":
                records.append(row)
    return records

async def run_evaluation():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    records = load_development_dataset()
    logger.info(f"Loaded {len(records)} development records.")
    
    service = VerificationService()
    v2_results = []
    
    # Evaluate candidates with their specific target language and market
    for r in records:
        nc = NormalizedCandidate(
            original_url=r["homepage_url"],
            normalized_url=r["homepage_url"],
            homepage_url=r["homepage_url"],
            registered_domain=r["domain"],
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
            expected_language="ja" if r.get("market") == "JP" else ("fr" if r.get("market") == "CA-FR" else "en"),
            expected_market=r.get("market")
        )
        try:
            resp = await service.verify_candidates(req)
            if resp.results:
                v2_results.append(resp.results[0])
        except Exception as e:
            logger.error(f"Error evaluating {r['domain']}: {e}")
    
    # We will compute metrics for various thresholds offline
    thresholds_to_test = []
    for vt in [70, 75, 80]:
        for gm in [18, 20, 22]:
            for mm in [14, 16, 18]:
                for mkm in [8, 10]:
                    for tm in [3, 4]:
                        thresholds_to_test.append({
                            "verified_threshold": vt,
                            "uncertain_threshold": 50,
                            "gaming_minimum": gm,
                            "media_minimum": mm,
                            "market_minimum": mkm,
                            "technical_minimum": tm
                        })
                        
    logger.info(f"Evaluating {len(thresholds_to_test)} threshold candidates offline.")
    
    def evaluate_threshold(t: Dict[str, int]) -> Dict[str, Any]:
        tp, fp, fn, tn, abstentions = 0, 0, 0, 0, 0
        for res in v2_results:
            domain = res.registered_domain
            expected_row = next(r for r in records if r["domain"] == domain)
            if expected_row.get("dataset_split") == "test":
                raise ValueError(f"CRITICAL ERROR: Protected test row {domain} entered tuning!")
            expected = expected_row["expected_label"]
            
            # Apply threshold
            if res.hard_rejection_rule:
                decision = "rejected"
            elif res.total_score >= t["verified_threshold"]:
                if res.gaming_score >= t["gaming_minimum"] and res.media_score >= t["media_minimum"] and res.market_score >= t["market_minimum"] and res.technical_score >= t["technical_minimum"]:
                    decision = "verified"
                else:
                    decision = "uncertain"
            elif res.total_score >= t["uncertain_threshold"]:
                decision = "uncertain"
            else:
                if res.technical_score < t["technical_minimum"]:
                    decision = "uncertain"
                else:
                    decision = "rejected"
                    
            is_expected_pos = (expected == "gaming_media")
            is_predicted_pos = (decision == "verified")
            
            if decision == "uncertain": abstentions += 1
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
    
    # 1. Prefer zero false positives
    # 2. Minimize false positives
    # 3. Maximize recall
    # 4. Use F1
    # 5. Maximize prediction coverage
    # 6. Prefer simpler thresholds (lower thresholds generally)
    
    def sort_key(cr):
        m = cr["metrics"]
        t = cr["thresholds"]
        return (
            -m["fp"], # minimize fp (so higher negative is better)
            m["recall"], # maximize recall
            m["f1"], # maximize f1
            m["coverage"], # maximize coverage
            -t["verified_threshold"], # simpler = lower thresholds? Actually, simpler = higher? Prompt says "Prefer simpler thresholds when performance is similar"
        )
        
    best_candidate = max(candidate_results, key=sort_key)
    
    with open(RESULTS_DIR / "phase5_threshold_comparison.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["VT", "GM", "MM", "MKM", "TM", "Precision", "Recall", "F1", "FP", "FN", "Abstentions", "Coverage"])
        for cr in sorted(candidate_results, key=sort_key, reverse=True):
            t = cr["thresholds"]
            m = cr["metrics"]
            writer.writerow([t["verified_threshold"], t["gaming_minimum"], t["media_minimum"], t["market_minimum"], t["technical_minimum"],
                             f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['f1']:.3f}", m['fp'], m['fn'], m['abstentions'], f"{m['coverage']:.3f}"])
                             
    # Re-apply best to generate predictions
    t_best = best_candidate["thresholds"]
    best_metrics = best_candidate["metrics"]
    
    predictions_csv = []
    for res in v2_results:
        domain = res.registered_domain
        expected = next(r["expected_label"] for r in records if r["domain"] == domain)
        if res.hard_rejection_rule:
            decision = "rejected"
            reason = f"Hard rejection: {res.hard_rejection_rule}"
        elif res.total_score >= t_best["verified_threshold"]:
            if res.gaming_score >= t_best["gaming_minimum"] and res.media_score >= t_best["media_minimum"] and res.market_score >= t_best["market_minimum"] and res.technical_score >= t_best["technical_minimum"]:
                decision = "verified"
                reason = "Met all component minimums and verified threshold."
            else:
                decision = "uncertain"
                reason = "Met verified total but missed component minimums."
        elif res.total_score >= t_best["uncertain_threshold"]:
            decision = "uncertain"
            reason = "Score in uncertain range."
        else:
            if res.technical_score < t_best["technical_minimum"]:
                decision = "uncertain"
                reason = "Low total score, but technical confidence too low for rejection."
            else:
                decision = "rejected"
                reason = "Total score below uncertain threshold."
                
        predictions_csv.append({
            "domain": domain,
            "expected_label": expected,
            "predicted_status": decision,
            "total_score": res.total_score,
            "gaming_score": res.gaming_score,
            "media_score": res.media_score,
            "market_score": res.market_score,
            "activity_score": res.activity_score,
            "technical_score": res.technical_score,
            "contextual_deductions": res.contextual_deductions,
            "hard_rejection_rule": res.hard_rejection_rule,
            "decision_reason": reason
        })
        
    with open(RESULTS_DIR / "phase5_development_predictions.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=predictions_csv[0].keys())
        writer.writeheader()
        writer.writerows(predictions_csv)
        
    with open(RESULTS_DIR / "phase5_development_metrics.json", "w", encoding="utf-8") as f:
        json.dump(best_metrics, f, indent=2)
        
    # Generate Frozen Config
    vocab_hash = get_vocabulary_hash()
    config_hash_input = f"{vocab_hash}-{t_best['verified_threshold']}-{t_best['uncertain_threshold']}-{t_best['gaming_minimum']}-{t_best['media_minimum']}-{t_best['market_minimum']}-{t_best['technical_minimum']}"
    import hashlib
    config_hash = hashlib.sha256(config_hash_input.encode('utf-8')).hexdigest()[:8]
    
    frozen_config = {
        "classifier_version": "v2_multilingual_explainable",
        "vocabulary_version": "v2.0",
        "vocabulary_hash": vocab_hash,
        "signal_weights": "Dynamic via rules_v2.py (normalized evidence)",
        "contextual_deductions": "store (-40), developer (-40), hardware (-30), casino (-80)",
        "hard_rejection_definitions": ["dominant_ecommerce_store", "game_developer_corporate_site", "game_publisher_marketing_site", "casino_or_betting_site"],
        "verified_threshold": t_best["verified_threshold"],
        "uncertain_threshold": t_best["uncertain_threshold"],
        "component_minimums": {
            "gaming": t_best["gaming_minimum"],
            "media": t_best["media_minimum"],
            "market": t_best["market_minimum"],
            "technical": t_best["technical_minimum"]
        },
        "configuration_hash": config_hash,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "development_selection_objective": "1. Zero FP, 2. Max Recall, 3. F1, 4. Coverage"
    }
    
    with open("backend/evaluation/phase5_frozen_configuration.json", "w", encoding="utf-8") as f:
        json.dump(frozen_config, f, indent=2)
        
    # Write analysis and selection
    with open(RESULTS_DIR / "phase5_threshold_selection.md", "w", encoding="utf-8") as f:
        f.write("# Phase 5 Threshold Selection\n\n")
        f.write(f"Evaluated {len(thresholds_to_test)} candidates.\n\n")
        f.write(f"Selected: {t_best}\n\n")
        f.write(f"Metrics: {best_metrics}\n\n")
        
    with open(RESULTS_DIR / "phase5_development_error_analysis.md", "w", encoding="utf-8") as f:
        f.write("# Phase 5 Development Error Analysis\n\n")
        for p in predictions_csv:
            is_fp = (p["expected_label"] != "gaming_media" and p["predicted_status"] == "verified")
            is_fn = (p["expected_label"] == "gaming_media" and p["predicted_status"] != "verified")
            if is_fp or is_fn:
                f.write(f"## {p['domain']} ({p['expected_label']} -> {p['predicted_status']})\n")
                f.write(f"* Scores: Total: {p['total_score']} (G:{p['gaming_score']} M:{p['media_score']} Mk:{p['market_score']} A:{p['activity_score']} T:{p['technical_score']})\n")
                f.write(f"* Deductions: {p['contextual_deductions']} HR: {p['hard_rejection_rule']}\n")
                f.write(f"* Reason: {p['decision_reason']}\n\n")

if __name__ == "__main__":
    import sys
    if "--fresh" in sys.argv or "--resume" in sys.argv:
        asyncio.run(run_evaluation())
