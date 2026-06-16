import asyncio
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.search import NormalizedCandidate
from app.schemas.fetch import FetchRequest
from app.services.fetch_service import FetchService
from app.verification.html_analyzer import HtmlAnalyzer
from app.verification.classifier import Classifier

EVAL_CSV_PATH = Path(__file__).resolve().parent / "gaming_media_evaluation.csv"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
PREDICTIONS_CSV_PATH = RESULTS_DIR / "acquisition_classifier_predictions.csv"
METRICS_JSON_PATH = RESULTS_DIR / "acquisition_classifier_metrics.json"

async def run_evaluation():
    print(f"Loading evaluation dataset from {EVAL_CSV_PATH}...")
    
    records = []
    with open(EVAL_CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
            
    print(f"Loaded {len(records)} records. Starting fetch and classification...")
    
    fetch_service = FetchService()
    classifier = Classifier()
    
    results = []
    
    # We process sequentially to avoid overwhelming the system
    # but internally acquire_evidence_batch limits concurrency.
    # Actually, we can batch them for speed, but sequentially is safer for logging.
    
    for idx, row in enumerate(records):
        domain = row["domain"]
        homepage_url = row["homepage_url"]
        expected_label = row["expected_label"]
        
        print(f"[{idx+1}/{len(records)}] Processing {domain}...")
        
        candidate = NormalizedCandidate(
            original_url=homepage_url,
            normalized_url=homepage_url,
            homepage_url=homepage_url,
            registered_domain=domain,
            title="",
            query_text="",
            provider="manual",
            result_position=1
        )
        
        req = FetchRequest(candidates=[candidate], use_homepage_url=True)
        acq_results, _ = await fetch_service.acquire_evidence_batch(req)
        
        if not acq_results:
            results.append({
                "domain": domain,
                "expected_label": expected_label,
                "predicted_status": "rejected", # Default for fetch failure
                "best_score": 0,
                "pages_analyzed": 0,
                "best_page_method": "none",
                "predictions": []
            })
            continue
            
        acq = acq_results[0]
        pages_to_analyze = []
        if acq.primary_page:
            pages_to_analyze.append(acq.primary_page)
        pages_to_analyze.extend(acq.supporting_pages)
        
        best_score = -1
        best_status = "rejected"
        best_method = "none"
        page_predictions = []
        
        current_time = datetime.now(timezone.utc)
        
        for p in pages_to_analyze:
            if not p.success or not p.html:
                continue
                
            analyzer = HtmlAnalyzer(p.html)
            signals = analyzer.analyze()
            
            clf_result = classifier.classify(
                requested_url=p.requested_url,
                final_url=p.final_url,
                registered_domain=p.registered_domain,
                signals=signals,
                current_time=current_time
            )
            
            page_predictions.append({
                "url": p.final_url,
                "method": getattr(p, "fetch_method", "http"),
                "score": clf_result.score,
                "status": clf_result.verification_status
            })
            
            # Update best score and status
            # Status priority: verified > uncertain > rejected
            
            is_better = False
            if clf_result.verification_status == "verified" and best_status != "verified":
                is_better = True
            elif clf_result.verification_status == "uncertain" and best_status == "rejected":
                is_better = True
            elif clf_result.verification_status == best_status and clf_result.score > best_score:
                is_better = True
                
            if is_better:
                best_status = clf_result.verification_status
                best_score = clf_result.score
                best_method = getattr(p, "fetch_method", "http")

        # If no pages succeeded, ensure best_score is 0
        if best_score == -1:
            best_score = 0
            
        results.append({
            "domain": domain,
            "expected_label": expected_label,
            "predicted_status": best_status,
            "best_score": best_score,
            "pages_analyzed": len(pages_to_analyze),
            "best_page_method": best_method,
            "predictions": page_predictions
        })
        
    print("Classification complete. Calculating metrics...")
    
    # Calculate metrics
    confusion_matrix = defaultdict(int)
    matches = 0
    total = len(results)
    
    for r in results:
        expected = r["expected_label"]
        predicted = r["predicted_status"]
        confusion_matrix[f"Expected:{expected}->Predicted:{predicted}"] += 1
        
        if expected == predicted:
            matches += 1
            
    accuracy = matches / total if total > 0 else 0
    
    metrics = {
        "total_domains": total,
        "accuracy": accuracy,
        "confusion_matrix": confusion_matrix
    }
    
    print(f"Overall Accuracy: {accuracy:.2f}")
    
    print(f"Writing predictions to {PREDICTIONS_CSV_PATH}...")
    with open(PREDICTIONS_CSV_PATH, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["domain", "expected_label", "predicted_status", "best_score", "pages_analyzed", "best_page_method"])
        for r in results:
            writer.writerow([
                r["domain"],
                r["expected_label"],
                r["predicted_status"],
                r["best_score"],
                r["pages_analyzed"],
                r["best_page_method"]
            ])
            
    print(f"Writing metrics to {METRICS_JSON_PATH}...")
    with open(METRICS_JSON_PATH, mode="w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
        
    print("Phase 4B execution complete!")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
