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
from app.schemas.fetch import FetchRequest
from app.services.fetch_service import FetchService

RESULTS_DIR = "evaluation/results"
PREDICTIONS_CSV = os.path.join(RESULTS_DIR, "revised_fetch_results.csv")
METRICS_JSON = os.path.join(RESULTS_DIR, "revised_fetch_metrics.json")
CHECKPOINT_JSON = os.path.join(RESULTS_DIR, "revised_fetch_checkpoint.json")
REPORT_MD = os.path.join(RESULTS_DIR, "fetch_reliability_comparison.md")
DATASET_PATH = "evaluation/gaming_media_evaluation.csv"

# Make sure baseline artifacts are not touched
BASELINE_FILES = [
    "baseline_predictions.csv",
    "baseline_raw_results.json",
    "baseline_metrics.json",
    "baseline_checkpoint.json",
    "baseline_report.md",
    "baseline_error_analysis.md"
]

def check_baseline_protection(filepath: str):
    basename = os.path.basename(filepath)
    if basename in BASELINE_FILES:
        raise ValueError(f"Attempting to overwrite protected baseline artifact: {basename}")

async def run_evaluation(resume: bool, fresh: bool):
    if fresh:
        for f in [PREDICTIONS_CSV, METRICS_JSON, CHECKPOINT_JSON, REPORT_MD]:
            check_baseline_protection(f)
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
    
    service = FetchService()
    results_map = checkpoint_data
    
    for i, record in enumerate(records):
        domain = record["domain"]
        if domain in processed_domains:
            print(f"Skipping {domain} (already processed)")
            continue
            
        print(f"[{i+1}/{len(records)}] Fetching {domain}...")
        
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
        
        req = FetchRequest(
            candidates=[candidate],
            use_homepage_url=True,
            include_html_preview=False
        )
        
        try:
            await asyncio.sleep(1.0)
            
            # Use acquire_evidence_batch directly to get full AcquisitionResult
            acq_results, _ = await service.acquire_evidence_batch(req)
            if acq_results:
                res = acq_results[0]
                
                # Make serializable
                def page_to_dict(p):
                    if not p: return None
                    d = p.model_dump(mode='json')
                    if d.get("html"): d["html"] = None # Avoid saving huge HTML in checkpoint
                    return d
                
                res_dict = {
                    "domain": res.domain,
                    "fetch_attempts": res.fetch_attempts,
                    "transport_success": res.transport_success,
                    "usable_evidence_found": res.usable_evidence_found,
                    "primary_page": page_to_dict(res.primary_page),
                    "supporting_pages": [page_to_dict(p) for p in res.supporting_pages],
                    "feed_entries_count": len(res.feed_entries),
                    "sitemap_candidates_count": len(res.sitemap_candidates)
                }
                
                results_map[domain] = {
                    "record": record, # contains target_market, language, etc.
                    "result": res_dict
                }
            else:
                print(f"No result returned for {domain}")
                results_map[domain] = {"record": record, "result": None}
                
        except Exception as e:
            print(f"Failed to process {domain}: {e}")
            results_map[domain] = {"record": record, "result": None}
            
        with open(CHECKPOINT_JSON, "w", encoding="utf-8") as f:
            json.dump(results_map, f, indent=2)

    print("Fetch evaluation complete. Generating reports...")
    generate_reports(records, results_map)

def generate_reports(records, results_map):
    predictions = []
    
    metrics = {
        "development": {"total": 0, "transport_success": 0, "usable_evidence_found": 0, "total_attempts": 0, "failures": {}},
        "test": {"total": 0, "transport_success": 0, "usable_evidence_found": 0, "total_attempts": 0, "failures": {}},
        "overall": {"total": 0, "transport_success": 0, "usable_evidence_found": 0, "total_attempts": 0, "failures": {}}
    }
    
    for row in records:
        domain = row["domain"]
        split = row["dataset_split"]
        data = results_map.get(domain)
        if not data or not data["result"]:
            continue
            
        res = data["result"]
        
        # Determine failure category
        fail_cat = None
        if not res["usable_evidence_found"] and res.get("primary_page"):
            fail_cat = res["primary_page"].get("failure_category") or "unknown"
            if res["primary_page"].get("success") and not res["usable_evidence_found"]:
                if res["primary_page"].get("javascript_shell_detected"):
                    fail_cat = "javascript_shell"
                elif res["primary_page"].get("challenge_detected"):
                    fail_cat = "challenge_page"
                else:
                    fail_cat = "insufficient_content"
                    
        pred_row = {
            "domain": domain,
            "homepage_url": row["homepage_url"],
            "dataset_split": split,
            "transport_success": res["transport_success"],
            "usable_evidence_found": res["usable_evidence_found"],
            "fetch_attempts": res["fetch_attempts"],
            "primary_method": res.get("primary_page", {}).get("fetch_method", "http") if res.get("primary_page") else "http",
            "failure_category": fail_cat if fail_cat else "",
            "feed_entries_count": res["feed_entries_count"],
            "supporting_pages_count": len(res["supporting_pages"]),
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat()
        }
        predictions.append(pred_row)
        
        for scope in [split, "overall"]:
            metrics[scope]["total"] += 1
            if res["transport_success"]: metrics[scope]["transport_success"] += 1
            if res["usable_evidence_found"]: metrics[scope]["usable_evidence_found"] += 1
            metrics[scope]["total_attempts"] += res["fetch_attempts"]
            
            if not res["usable_evidence_found"]:
                fcat = fail_cat or "unknown"
                metrics[scope]["failures"][fcat] = metrics[scope]["failures"].get(fcat, 0) + 1

    if predictions:
        with open(PREDICTIONS_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(predictions[0].keys()))
            writer.writeheader()
            writer.writerows(predictions)
            
    with open(METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("# Fetch Reliability Comparison Report\n\n")
        f.write("Evaluation of Phase 4A improvements without verifying classification.\n\n")
        
        for scope in ["development", "test", "overall"]:
            m = metrics[scope]
            if m["total"] == 0: continue
            f.write(f"## {scope.capitalize()} Metrics\n")
            f.write(f"- Total Domains: {m['total']}\n")
            f.write(f"- Transport Success Rate: {m['transport_success']}/{m['total']} ({m['transport_success']/m['total']:.2%})\n")
            f.write(f"- Usable Evidence Rate: {m['usable_evidence_found']}/{m['total']} ({m['usable_evidence_found']/m['total']:.2%})\n")
            f.write(f"- Average Attempts per Domain: {m['total_attempts']/m['total']:.2f}\n\n")
            
            if m["failures"]:
                f.write(f"### Remaining Failures ({sum(m['failures'].values())})\n")
                for cat, count in sorted(m["failures"].items(), key=lambda x: x[1], reverse=True):
                    f.write(f"- {cat}: {count}\n")
            f.write("\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_evaluation(args.resume, args.fresh))