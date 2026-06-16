import sys
import os
import csv
import json
import hashlib
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import get_settings
from app.services.verification_service import VerificationService
from app.schemas.verification import VerificationRequest, NormalizedCandidate
from app.verification.classifier_v2 import ClassifierV2

RESULTS_DIR = Path("evaluation/results")
DATASET_PATH = Path("evaluation/gaming_media_evaluation.csv")
FROZEN_CONFIG_PATH = Path("evaluation/phase5d_frozen_configuration.json")
LOCK_PATH = RESULTS_DIR / "phase6_protected_test.lock.json"
CHECKPOINT_PATH = RESULTS_DIR / "phase6_checkpoint.json"

# These hashes must match the committed state
EXPECTED_DATASET_HASH = "ab160badfdcf2b478450006ae168b020f0aead9194875a579937884f7c2830aa"
EXPECTED_SCORING_HASH = "323a9aef84adcbffa04c2de619983fefab8bf694b7449994eddaa46e8b2fdd42"

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def verify_hashes():
    """Verify that scoring source files and dataset have not changed since Phase 5D commit."""
    dataset_hash = file_hash(DATASET_PATH)
    if dataset_hash != EXPECTED_DATASET_HASH:
        raise RuntimeError(
            f"Dataset hash mismatch!\n  Expected: {EXPECTED_DATASET_HASH}\n  Got:      {dataset_hash}\n"
            "The evaluation dataset has been modified since Phase 5D was frozen. Aborting."
        )

    scoring_files = sorted([
        "app/verification/classifier_v2.py",
        "app/verification/rules_v2.py",
        "app/verification/html_analyzer.py",
        "app/schemas/verification.py",
    ])
    combined = b"".join(Path(f).read_bytes() for f in scoring_files)
    scoring_hash = hashlib.sha256(combined).hexdigest()
    if scoring_hash != EXPECTED_SCORING_HASH:
        raise RuntimeError(
            f"Scoring-rule hash mismatch!\n  Expected: {EXPECTED_SCORING_HASH}\n  Got:      {scoring_hash}\n"
            "Classifier source has changed since Phase 5D was frozen. Aborting."
        )

def load_test_dataset():
    """Load only test rows. Raises if any development row appears in the test split."""
    records = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["dataset_split"] == "development":
                continue  # skip; development rows must never enter Phase 6
            if row["dataset_split"] == "test":
                records.append(row)
    # Safety assert: ensure no dev domain made it through
    test_domains = {r["domain"] for r in records}
    dev_domains = set()
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["dataset_split"] == "development":
                dev_domains.add(row["domain"])
    overlap = test_domains & dev_domains
    if overlap:
        raise RuntimeError(
            f"Development domain(s) found in test split: {overlap}. Dataset integrity violated. Aborting."
        )
    return records

def load_frozen_config():
    with open(FROZEN_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def compute_metrics(predictions):
    """Compute both strict and review-aware binary metrics from predictions."""
    # Strict accuracy
    strict_correct = sum(1 for p in predictions if p.get("is_strictly_correct"))
    strict_accuracy = strict_correct / len(predictions) if predictions else 0

    # Review-aware binary metrics (exclude uncertain expected label rows)
    binary = [p for p in predictions if p["expected_label"] != "uncertain"]
    tp = sum(1 for p in binary if p["binary_outcome"] == "TP")
    fp = sum(1 for p in binary if p["binary_outcome"] == "FP")
    tn = sum(1 for p in binary if p["binary_outcome"] == "TN")
    fn = sum(1 for p in binary if p["binary_outcome"] == "FN")
    # Abstentions: not in TP/FP/TN/FN
    abstentions = sum(1 for p in binary if p.get("abstained", False))
    decided = tp + fp + tn + fn
    expected_positives = sum(1 for p in binary if p["expected_label"] == "gaming_media")

    decision_coverage = decided / len(binary) if binary else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    decided_recall = tp / (tp + fn) if (tp + fn) > 0 else None
    operational_recall = tp / expected_positives if expected_positives > 0 else 0
    f1 = (2 * precision * decided_recall / (precision + decided_recall)
          if precision is not None and decided_recall is not None and (precision + decided_recall) > 0 else None)
    specificity = tn / (tn + fp) if (tn + fp) > 0 else None

    # Market distribution
    market_counts = {}
    for p in predictions:
        ms = p.get("market_status", "unknown")
        market_counts[ms] = market_counts.get(ms, 0) + 1

    # Relevance-label accuracy (excluding abstentions/fetch_failed)
    relevance_correct = sum(
        1 for p in binary
        if not p.get("abstained") and
        (p["relevance_label"] == "gaming_media") == (p["expected_label"] == "gaming_media")
    )
    relevance_accuracy = relevance_correct / decided if decided > 0 else 0

    return {
        "strict_accuracy": strict_accuracy,
        "binary_metrics": {
            "eligible_binary_rows": len(binary),
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives_decided": tn,
            "false_negatives_decided": fn,
            "abstentions": abstentions,
            "decision_coverage": decision_coverage,
            "precision": precision,
            "decided_prediction_recall": decided_recall,
            "operational_positive_recall": operational_recall,
            "f1": f1,
            "specificity": specificity,
        },
        "market_status_distribution": market_counts,
        "relevance_label_accuracy": relevance_accuracy,
    }

def load_baseline_metrics():
    path = RESULTS_DIR / "baseline_metrics.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

async def run_protected_evaluation(resume=False):
    """Execute Phase 6 protected test evaluation. Runs exactly once."""
    if LOCK_PATH.exists():
        raise RuntimeError(
            "Phase 6 protected test lock file already exists at:\n"
            f"  {LOCK_PATH}\n"
            "Refusing to run again. This evaluation must only be executed once."
        )

    # Pre-flight checks
    verify_hashes()
    config = load_frozen_config()

    if config.get("evidence_safety_gate") != "enabled":
        raise RuntimeError("evidence_safety_gate must be 'enabled' in frozen configuration.")

    records = load_test_dataset()
    print(f"Loaded {len(records)} test rows.")

    service = VerificationService()

    # Load checkpoint for resume
    checkpoint_data = {}
    if resume and CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            checkpoint_data = json.load(f)
        print(f"Resumed from checkpoint: {len(checkpoint_data)} domains already processed.")
    elif not resume and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    # ── PHASE 1: Generate predictions before reading expected labels ──────────
    for r in records:
        domain = r["domain"]
        if domain in checkpoint_data:
            continue

        # Only allowed fields enter the request
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
        expected_lang = "ja" if r.get("target_market") == "Japan" else (
            "fr" if r.get("language") == "fr" else "en"
        )
        req = VerificationRequest(
            candidates=[nc],
            classifier_version="v2_multilingual_explainable",
            verified_threshold=config["verified_threshold"],
            uncertain_threshold=config["uncertain_threshold"],
            gaming_minimum=config["gaming_minimum"],
            media_minimum=config["media_minimum"],
            technical_minimum=config["technical_minimum"],
            market_minimum=config["market_minimum"],
            expected_language=expected_lang,
            expected_market=r.get("target_market")
        )

        try:
            resp = await service.verify_candidates(req)
            if resp.results:
                res = resp.results[0]
                usable_ev = (
                    hasattr(res, 'acquisition_context') and
                    res.acquisition_context and
                    res.acquisition_context.usable_acquisition_evidence
                ) or (
                    res.predicted_status not in ["fetch_failed", "uncertain"]
                )

                checkpoint_data[domain] = {
                    "domain": domain,
                    "homepage_url": r["homepage_url"],
                    "dataset_split": "test",
                    "transport_success": res.predicted_status != "fetch_failed",
                    "usable_evidence_found": usable_ev,
                    "usable_acquisition_evidence": usable_ev,
                    "meaningful_relevance_evidence": usable_ev,
                    "primary_fetch_method": "http",
                    "supporting_page_count": 0,
                    "feed_entry_count": 0,
                    "structured_article_evidence_count": 0,
                    "predicted_status": res.predicted_status,
                    "relevance_label": res.relevance_label,
                    "market_status": res.market_status,
                    "gaming_score": res.gaming_score,
                    "media_score": res.media_score,
                    "market_score": res.market_score,
                    "activity_score": res.activity_score,
                    "technical_score": res.technical_score,
                    "component_sum": getattr(res, "component_sum", 0),
                    "contextual_deductions": getattr(res, "contextual_deductions", 0),
                    "total_score": res.total_score,
                    "hard_rejection_rule": getattr(res, "hard_rejection_rule", None) or "None",
                    "hard_rejection_evidence": "|".join(
                        [str(e) for e in (getattr(res, "hard_rejection_evidence", []) or [])]
                    ) or "None",
                    "decision_override": getattr(res, "decision_override", None) or "None",
                    "decision_reason": res.decision_reason,
                    "confidence": getattr(res, "confidence", "low"),
                    "evaluation_timestamp": datetime.now(timezone.utc).isoformat()
                }

                # Persist checkpoint after each domain
                with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
                    json.dump(checkpoint_data, f, indent=2)
        except Exception as e:
            print(f"Error processing {domain}: {e}")

    # Write raw results before joining labels
    with open(RESULTS_DIR / "phase6_test_raw_results.json", "w", encoding="utf-8") as f:
        json.dump(checkpoint_data, f, indent=2)

    # ── PHASE 2: Join expected labels ONLY after all predictions are finalised ─
    predictions = []
    for r in records:
        domain = r["domain"]
        expected_label = r["expected_label"]  # read labels HERE for comparison only
        p = checkpoint_data.get(domain)
        if not p:
            continue

        p = dict(p)
        p["expected_label"] = expected_label

        is_strictly_correct = (
            (p["predicted_status"] == "verified" and expected_label == "gaming_media") or
            (p["predicted_status"] == "rejected" and expected_label == "not_gaming_media") or
            (p["predicted_status"] == "uncertain" and expected_label == "uncertain")
        )
        p["is_strictly_correct"] = is_strictly_correct

        binary_outcome = "None"
        abstained = True
        if expected_label != "uncertain":
            abstained = p["predicted_status"] in ["uncertain", "fetch_failed"]
            if p["predicted_status"] == "verified" and expected_label == "gaming_media":
                binary_outcome = "TP"
            elif p["predicted_status"] == "verified" and expected_label != "gaming_media":
                binary_outcome = "FP"
            elif p["predicted_status"] == "rejected" and expected_label == "not_gaming_media":
                binary_outcome = "TN"
            elif p["predicted_status"] == "rejected" and expected_label == "gaming_media":
                binary_outcome = "FN"

        p["binary_outcome"] = binary_outcome
        p["abstained"] = abstained
        predictions.append(p)

    # Write predictions CSV
    with open(RESULTS_DIR / "phase6_test_predictions.csv", "w", newline="", encoding="utf-8") as f:
        if predictions:
            writer = csv.DictWriter(f, fieldnames=predictions[0].keys())
            writer.writeheader()
            writer.writerows(predictions)

    # ── Metrics ───────────────────────────────────────────────────────────────
    metrics = compute_metrics(predictions)
    metrics["total_test_rows"] = len(predictions)
    metrics["transport_success_count"] = sum(1 for p in predictions if p["transport_success"])
    metrics["usable_evidence_count"] = sum(1 for p in predictions if p["usable_evidence_found"])
    metrics["verified_count"] = sum(1 for p in predictions if p["predicted_status"] == "verified")
    metrics["rejected_count"] = sum(1 for p in predictions if p["predicted_status"] == "rejected")
    metrics["uncertain_count"] = sum(1 for p in predictions if p["predicted_status"] == "uncertain")
    metrics["fetch_failed_count"] = sum(1 for p in predictions if p["predicted_status"] == "fetch_failed")
    metrics["evidence_gate_overrides"] = sum(
        1 for p in predictions if p.get("decision_override") == "insufficient_evidence"
    )

    with open(RESULTS_DIR / "phase6_test_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # ── Comparison vs Phase 4B baseline ────────────────────────────────────────
    baseline = load_baseline_metrics()
    comparison_lines = [
        "# Phase 4B vs Phase 6 Comparison\n\n",
        "Phase 4B used the unchanged baseline classifier.\n",
        "Phase 6 uses the frozen multilingual v2 classifier plus the frozen evidence-safety gate.\n\n",
        "| Metric | Phase 4B (Baseline) | Phase 6 (v2) |\n",
        "|--------|--------------------|--------------|\n",
    ]
    bm = metrics["binary_metrics"]
    for label, b_key, p6_val in [
        ("Decision Coverage", "decision_coverage", f"{bm['decision_coverage']:.1%}"),
        ("Precision", "precision", f"{bm['precision']:.1%}" if bm["precision"] is not None else "N/A"),
        ("Operational Recall", "operational_positive_recall", f"{bm['operational_positive_recall']:.1%}"),
        ("F1", "f1", f"{bm['f1']:.3f}" if bm["f1"] is not None else "N/A"),
        ("False Positives", "false_positives", str(bm["false_positives"])),
        ("Abstentions", "abstentions", str(bm["abstentions"])),
    ]:
        b_val = baseline.get(b_key, "N/A")
        comparison_lines.append(f"| {label} | {b_val} | {p6_val} |\n")

    with open(RESULTS_DIR / "phase6_baseline_vs_v2_comparison.md", "w", encoding="utf-8") as f:
        f.writelines(comparison_lines)

    # ── Error analysis ─────────────────────────────────────────────────────────
    with open(RESULTS_DIR / "phase6_test_error_analysis.md", "w", encoding="utf-8") as f:
        f.write("# Phase 6 Error Analysis\n\n")
        f.write("> Do not modify any classifier or configuration after reviewing these errors.\n\n")

        fps = [p for p in predictions if p["binary_outcome"] == "FP"]
        fns = [p for p in predictions if p["binary_outcome"] == "FN"]
        abstained_pos = [p for p in predictions
                        if p["expected_label"] == "gaming_media" and p.get("abstained")]
        abstained_neg = [p for p in predictions
                        if p["expected_label"] == "not_gaming_media" and p.get("abstained")]
        gate_overrides = [p for p in predictions if p.get("decision_override") == "insufficient_evidence"]

        f.write(f"## False Positives ({len(fps)})\n")
        for p in fps:
            f.write(f"- {p['domain']}: score={p['total_score']}, reason={p['decision_reason']}\n")

        f.write(f"\n## False Negatives among Decided Predictions ({len(fns)})\n")
        for p in fns:
            f.write(f"- {p['domain']}: score={p['total_score']}, reason={p['decision_reason']}\n")

        f.write(f"\n## Abstained Expected Positives ({len(abstained_pos)})\n")
        for p in abstained_pos:
            f.write(f"- {p['domain']}: status={p['predicted_status']}, override={p.get('decision_override','None')}\n")

        f.write(f"\n## Abstained Expected Negatives ({len(abstained_neg)})\n")
        for p in abstained_neg:
            f.write(f"- {p['domain']}: status={p['predicted_status']}\n")

        f.write(f"\n## Evidence Gate Overrides ({len(gate_overrides)})\n")
        for p in gate_overrides:
            f.write(f"- {p['domain']}: score={p['total_score']}\n")

    # ── Phase 6 summary report ─────────────────────────────────────────────────
    bm = metrics["binary_metrics"]
    with open(RESULTS_DIR / "phase6_test_report.md", "w", encoding="utf-8") as f:
        f.write("# Phase 6 Protected Test Report\n\n")
        f.write(f"**Classifier**: v2_multilingual_explainable + evidence-safety gate  \n")
        f.write(f"**Test rows**: {metrics['total_test_rows']}  \n")
        f.write(f"**Baseline remains production default**: YES  \n\n")
        f.write("## Transport & Evidence\n\n")
        f.write(f"- Transport success: {metrics['transport_success_count']}\n")
        f.write(f"- Usable evidence: {metrics['usable_evidence_count']}\n")
        f.write(f"- Evidence gate overrides: {metrics['evidence_gate_overrides']}\n\n")
        f.write("## Predictions\n\n")
        f.write(f"- Verified: {metrics['verified_count']}\n")
        f.write(f"- Rejected: {metrics['rejected_count']}\n")
        f.write(f"- Uncertain: {metrics['uncertain_count']}\n")
        f.write(f"- Fetch failed: {metrics['fetch_failed_count']}\n\n")
        f.write("## Binary Metrics\n\n")
        f.write(f"- Eligible binary rows: {bm['eligible_binary_rows']}\n")
        f.write(f"- True positives: {bm['true_positives']}\n")
        f.write(f"- False positives: {bm['false_positives']}\n")
        f.write(f"- True negatives (decided): {bm['true_negatives_decided']}\n")
        f.write(f"- False negatives (decided): {bm['false_negatives_decided']}\n")
        f.write(f"- Abstentions: {bm['abstentions']}\n")
        f.write(f"- Decision coverage: {bm['decision_coverage']:.1%}\n")
        p = bm['precision']
        f.write(f"- Precision: {p:.1%}\n" if p is not None else "- Precision: N/A\n")
        dr = bm['decided_prediction_recall']
        f.write(f"- Decided-prediction recall: {dr:.1%}\n" if dr is not None else "- Decided-prediction recall: N/A\n")
        f.write(f"- Operational positive recall: {bm['operational_positive_recall']:.1%}\n")
        f1 = bm['f1']
        f.write(f"- F1: {f1:.3f}\n" if f1 is not None else "- F1: N/A\n")
        sp = bm['specificity']
        f.write(f"- Specificity: {sp:.1%}\n" if sp is not None else "- Specificity: N/A\n")
        f.write(f"\n- Strict accuracy: {metrics['strict_accuracy']:.1%}\n")
        f.write(f"- Relevance-label accuracy: {metrics['relevance_label_accuracy']:.1%}\n\n")
        f.write("## Market Status Distribution\n\n")
        for k, v in metrics["market_status_distribution"].items():
            f.write(f"- {k}: {v}\n")

    # ── Write completion lock ──────────────────────────────────────────────────
    lock_data = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "Phase 5D configuration hash": file_hash(FROZEN_CONFIG_PATH),
        "dataset hash": EXPECTED_DATASET_HASH,
        "test split hash": hashlib.sha256(
            json.dumps(sorted(checkpoint_data.keys())).encode()
        ).hexdigest(),
        "test row count": len(predictions),
        "runner version": "phase6_v1",
        "prediction file hash": file_hash(RESULTS_DIR / "phase6_test_predictions.csv"),
        "metrics file hash": file_hash(RESULTS_DIR / "phase6_test_metrics.json"),
        "raw results file hash": file_hash(RESULTS_DIR / "phase6_test_raw_results.json"),
    }
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(lock_data, f, indent=2)

    print("\nPhase 6 protected evaluation complete.")
    print(f"Lock written: {LOCK_PATH}")
    print(f"Test rows:    {len(predictions)}")
    bm = metrics["binary_metrics"]
    print(f"TP={bm['true_positives']}  FP={bm['false_positives']}  "
          f"TN={bm['true_negatives_decided']}  FN={bm['false_negatives_decided']}  "
          f"Abstain={bm['abstentions']}")
    print(f"Coverage={bm['decision_coverage']:.1%}  "
          f"OpRecall={bm['operational_positive_recall']:.1%}  "
          f"Precision={bm['precision']:.1%}" if bm['precision'] is not None else
          f"Coverage={bm['decision_coverage']:.1%}  OpRecall={bm['operational_positive_recall']:.1%}  Precision=N/A")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 6 Protected Test Evaluation")
    parser.add_argument("--run-once", action="store_true",
                        help="Execute the one-time protected test evaluation.")
    parser.add_argument("--resume", action="store_true",
                        help="Resume an interrupted (incomplete) run. Fails if lock already exists.")
    args = parser.parse_args()

    if args.run_once:
        asyncio.run(run_protected_evaluation(resume=False))
    elif args.resume:
        asyncio.run(run_protected_evaluation(resume=True))
    else:
        print("Usage: python run_phase6_protected_test_evaluation.py --run-once")
        print("       python run_phase6_protected_test_evaluation.py --resume   (incomplete run only)")
        sys.exit(1)
