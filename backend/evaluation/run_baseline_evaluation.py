import sys
import os
import csv
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.schemas.search import NormalizedCandidate
from app.schemas.verification import VerificationRequest, VerificationResult
from app.services.verification_service import VerificationService
from evaluation.metrics import (
    get_binary_outcome, calculate_strict_correctness, calculate_precision,
    calculate_recall, calculate_f1, calculate_specificity, calculate_accuracy,
    calculate_fpr, calculate_fnr, generate_binary_confusion_matrix, safe_div
)

RESULTS_DIR = "evaluation/results"
PREDICTIONS_CSV = os.path.join(RESULTS_DIR, "baseline_predictions.csv")
RAW_RESULTS_JSON = os.path.join(RESULTS_DIR, "baseline_raw_results.json")
METRICS_JSON = os.path.join(RESULTS_DIR, "baseline_metrics.json")
CHECKPOINT_JSON = os.path.join(RESULTS_DIR, "baseline_checkpoint.json")
REPORT_MD = os.path.join(RESULTS_DIR, "baseline_report.md")
ERROR_ANALYSIS_MD = os.path.join(RESULTS_DIR, "baseline_error_analysis.md")
DATASET_PATH = "evaluation/gaming_media_evaluation.csv"

async def run_evaluation(resume: bool, fresh: bool):
    if fresh:
        for f in [PREDICTIONS_CSV, RAW_RESULTS_JSON, METRICS_JSON, CHECKPOINT_JSON, REPORT_MD, ERROR_ANALYSIS_MD]:
            if os.path.exists(f):
                os.remove(f)

    if not os.path.exists(DATASET_PATH):
        print(f"Error: {DATASET_PATH} not found.")
        return

    records = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)

    checkpoint_data = {}
    if resume and os.path.exists(CHECKPOINT_JSON):
        with open(CHECKPOINT_JSON, "r", encoding="utf-8") as f:
            checkpoint_data = json.load(f)

    processed_domains = set(checkpoint_data.keys())
    
    # We will process sequentially with a small delay to avoid rate limiting
    service = VerificationService()
    
    results_map = checkpoint_data
    
    for i, record in enumerate(records):
        domain = record["domain"]
        if domain in processed_domains:
            print(f"Skipping {domain} (already processed)")
            continue
            
        print(f"[{i+1}/{len(records)}] Verifying {domain}...")
        
        url = record["homepage_url"] or f"https://{domain}/"
        candidate = NormalizedCandidate(
            original_url=url,
            normalized_url=url,
            homepage_url=url,
            registered_domain=domain,
            title=domain,
            query_text="",
            provider="manual",
            result_position=1
        )
        
        req = VerificationRequest(
            candidates=[candidate],
            include_evidence=True
        )
        
        try:
            # We enforce a small delay to be polite to the web
            await asyncio.sleep(1.0)
            
            preview_res = await service.verify_candidates(req)
            if preview_res.results:
                res = preview_res.results[0]
                
                # Make it JSON serializable
                res_dict = res.model_dump(mode='json')
                
                results_map[domain] = {
                    "record": record,
                    "result": res_dict
                }
            else:
                print(f"No result returned for {domain}")
                results_map[domain] = {
                    "record": record,
                    "result": None
                }
                
        except Exception as e:
            print(f"Failed to process {domain}: {e}")
            results_map[domain] = {
                "record": record,
                "result": None
            }
            
        # Save checkpoint
        with open(CHECKPOINT_JSON, "w", encoding="utf-8") as f:
            json.dump(results_map, f, indent=2)

    print("Verification complete. Generating reports...")
    generate_reports(records, results_map)

def generate_reports(records, results_map):
    predictions = []
    raw_results = {}
    
    metrics = {
        "development": {"total": 0, "correct": 0, "tp": 0, "tn": 0, "fp": 0, "fn": 0, "abstain": 0, "fetch_failed": 0, "verified": 0, "rejected": 0, "uncertain": 0, "eligible_binary": 0},
        "test": {"total": 0, "correct": 0, "tp": 0, "tn": 0, "fp": 0, "fn": 0, "abstain": 0, "fetch_failed": 0, "verified": 0, "rejected": 0, "uncertain": 0, "eligible_binary": 0},
        "overall": {"total": 0, "correct": 0, "tp": 0, "tn": 0, "fp": 0, "fn": 0, "abstain": 0, "fetch_failed": 0, "verified": 0, "rejected": 0, "uncertain": 0, "eligible_binary": 0}
    }
    
    for row in records:
        domain = row["domain"]
        split = row["dataset_split"]
        data = results_map.get(domain)
        if not data or not data["result"]:
            continue
            
        res = data["result"]
        raw_results[domain] = res
        
        status = res["verification_status"]
        expected = row["expected_label"]
        
        is_correct = calculate_strict_correctness(expected, status)
        binary_out = get_binary_outcome(expected, status)
        
        # Reason extraction
        reasons = [r["message"] for r in res.get("positive_reasons", []) + res.get("negative_reasons", [])]
        reason_str = " | ".join(reasons)
        
        pred_row = {
            "domain": domain,
            "homepage_url": row["homepage_url"],
            "expected_label": expected,
            "website_type": row["website_type"],
            "target_market": row["target_market"],
            "language": row["language"],
            "activity_status": row["activity_status"],
            "dataset_split": split,
            "raw_verifier_status": status,
            "mapped_prediction": status if status != "fetch_failed" else "uncertain",
            "gaming_score": res.get("gaming_relevance_score", 0),
            "editorial_score": res.get("editorial_structure_score", 0),
            "activity_score": res.get("activity_score", 0),
            "identity_score": res.get("publication_identity_score", 0),
            "negative_penalty": res.get("negative_penalty", 0),
            "raw_score": sum([res.get("gaming_relevance_score", 0), res.get("editorial_structure_score", 0), res.get("activity_score", 0), res.get("publication_identity_score", 0)]) - res.get("negative_penalty", 0),
            "bounded_score": res.get("score", 0),
            "confidence": res.get("confidence", 0),
            "fetch_status": "success" if res.get("fetch_success") else "failed",
            "fetch_error": res.get("fetch_error_code", ""),
            "verification_reason": reason_str,
            "positive_signals": json.dumps([r["code"] for r in res.get("positive_reasons", [])]),
            "negative_signals": json.dumps([r["code"] for r in res.get("negative_reasons", [])]),
            "market_evidence": json.dumps(res.get("market_evidence", [])),
            "is_strictly_correct": is_correct,
            "binary_outcome": binary_out,
            "abstained": binary_out == "ABSTAIN",
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat()
        }
        predictions.append(pred_row)
        
        # Update metrics
        for scope in [split, "overall"]:
            metrics[scope]["total"] += 1
            if is_correct: metrics[scope]["correct"] += 1
            if status == "verified": metrics[scope]["verified"] += 1
            elif status == "rejected": metrics[scope]["rejected"] += 1
            elif status == "uncertain": metrics[scope]["uncertain"] += 1
            elif status == "fetch_failed": metrics[scope]["fetch_failed"] += 1
            
            if expected != "uncertain":
                metrics[scope]["eligible_binary"] += 1
                if binary_out == "TP": metrics[scope]["tp"] += 1
                elif binary_out == "TN": metrics[scope]["tn"] += 1
                elif binary_out == "FP": metrics[scope]["fp"] += 1
                elif binary_out == "FN": metrics[scope]["fn"] += 1
                elif binary_out == "ABSTAIN": metrics[scope]["abstain"] += 1

    # Write predictions
    if predictions:
        with open(PREDICTIONS_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(predictions[0].keys()))
            writer.writeheader()
            writer.writerows(predictions)
            
    # Write raw results
    with open(RAW_RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, indent=2)
        
    # Calculate derived metrics
    derived_metrics = {}
    for scope in ["development", "test", "overall"]:
        m = metrics[scope]
        tp, fp, tn, fn = m["tp"], m["fp"], m["tn"], m["fn"]
        binary_predicted = tp + fp + tn + fn
        
        derived_metrics[scope] = {
            "total_rows": m["total"],
            "correct_rows": m["correct"],
            "incorrect_rows": m["total"] - m["correct"],
            "strict_accuracy": calculate_accuracy(m["correct"], m["total"]),
            "verified_count": m["verified"],
            "rejected_count": m["rejected"],
            "uncertain_count": m["uncertain"],
            "fetch_failed_count": m["fetch_failed"],
            "eligible_binary_rows": m["eligible_binary"],
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "abstentions": m["abstain"],
            "prediction_coverage": safe_div(binary_predicted, m["eligible_binary"]),
            "precision": calculate_precision(tp, fp),
            "recall": calculate_recall(tp, fn),
            "f1_score": calculate_f1(calculate_precision(tp, fp), calculate_recall(tp, fn)),
            "specificity": calculate_specificity(tn, fp),
            "binary_accuracy": calculate_accuracy(tp + tn, binary_predicted),
            "false_positive_rate": calculate_fpr(fp, tn),
            "false_negative_rate": calculate_fnr(fn, tp)
        }
        
    with open(METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(derived_metrics, f, indent=2)

    # Generate Markdown Report
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("# Baseline Evaluation Report\n\n")
        f.write("A controlled baseline measurement on a small manually reviewed MVP benchmark.\n\n")
        f.write("## 1. Purpose\nMeasure current verifier exactly as it exists before reliability improvements.\n\n")
        f.write("## 2. Dataset Composition\n50 real websites manually reviewed. 35 dev, 15 test.\n\n")
        f.write("## 3. Metric Policy\nStrict correctness requires exact matches. Binary metrics exclude `uncertain` expected labels. `fetch_failed` and `uncertain` predictions are counted as abstentions and reduce coverage.\n\n")
        f.write("## 4. Current Verifier Architecture\nRules-based heuristic combining gaming, editorial, activity, and identity scores minus a negative penalty.\n\n")
        
        for scope in ["development", "test", "overall"]:
            dm = derived_metrics[scope]
            f.write(f"## {scope.capitalize()} Metrics\n")
            f.write(f"- Strict Accuracy: {dm['strict_accuracy']:.2%}\n")
            f.write(f"- Precision: {dm['precision']:.2%}\n")
            f.write(f"- Recall: {dm['recall']:.2%}\n")
            f.write(f"- F1 Score: {dm['f1_score']:.2%}\n")
            f.write(f"- Coverage: {dm['prediction_coverage']:.2%}\n\n")

        f.write("## Abstention and Fetch-Failure Counts\n")
        f.write(f"Total Fetch Failed: {derived_metrics['overall']['fetch_failed_count']}\n")
        f.write(f"Total Uncertain: {derived_metrics['overall']['uncertain_count']}\n\n")
        
        f.write("## Statement\nNo verifier changes were made. This is purely a baseline measurement.\n")
        
    # Generate Error Analysis
    with open(ERROR_ANALYSIS_MD, "w", encoding="utf-8") as f:
        f.write("# Baseline Error Analysis\n\n")
        for pred in predictions:
            if not pred["is_strictly_correct"] or pred["binary_outcome"] in ["FP", "FN", "ABSTAIN"] or pred["expected_label"] == "uncertain":
                f.write(f"### {pred['domain']}\n")
                f.write(f"- Expected: {pred['expected_label']}\n")
                f.write(f"- Predicted: {pred['raw_verifier_status']}\n")
                f.write(f"- Type: {pred['website_type']}\n")
                f.write(f"- Binary Outcome: {pred['binary_outcome']}\n")
                f.write(f"- Scores: Gaming={pred['gaming_score']}, Editorial={pred['editorial_score']}, Activity={pred['activity_score']}, Identity={pred['identity_score']}, Penalty={pred['negative_penalty']}\n")
                f.write(f"- Reason: {pred['verification_reason']}\n\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_evaluation(args.resume, args.fresh))
