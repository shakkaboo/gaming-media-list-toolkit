import csv
import json
import sys
import os
import re
from collections import Counter

try:
    from app.services.candidate_processor import _get_canonical_domain
except ImportError:
    def _get_canonical_domain(url_or_domain: str) -> str:
        d = url_or_domain.replace("https://", "").replace("http://", "").split("/")[0]
        return d.removeprefix("www.")

def validate_and_summarize():
    filepath = "evaluation/gaming_media_evaluation.csv"
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        sys.exit(1)

    expected_columns = [
        "domain", "homepage_url", "expected_label", "website_type",
        "target_market", "language", "activity_status", "label_reason",
        "evidence_summary", "reviewer_notes", "dataset_split",
        "evidence_url_1", "evidence_url_2", "reviewed_at", "review_method"
    ]

    allowed_labels = {"gaming_media", "not_gaming_media", "uncertain"}
    allowed_website_types = {
        "gaming_publication", "general_media_gaming_section", "game_developer",
        "game_publisher", "gaming_retailer", "esports_organization",
        "forum_or_community", "hardware_or_technology", "creator_or_streaming_profile",
        "single_game_site", "inactive_or_archived_media", "unrelated", "ambiguous"
    }
    allowed_activity_statuses = {"active", "inactive", "unknown"}
    allowed_splits = {"development", "test"}
    fictitious_patterns = ["example.com", "localhost", "test"]

    domains = set()
    records = []

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        if header != expected_columns:
            print("Error: Incorrect columns.")
            sys.exit(1)

        for i, row in enumerate(reader):
            if len(row) != len(expected_columns):
                print(f"Error: Row {i+2} column count mismatch.")
                sys.exit(1)
            records.append(dict(zip(expected_columns, row)))

    if len(records) != 50:
        print(f"Error: Expected 50 records, found {len(records)}.")
        sys.exit(1)

    dev_count = 0
    test_count = 0
    
    dev_labels = set()
    test_labels = set()
    test_types = set()
    dev_types = set()

    summary = {
        "total_records": len(records),
        "label_counts": Counter(),
        "website_type_counts": Counter(),
        "market_counts": Counter(),
        "language_counts": Counter(),
        "activity_status_counts": Counter(),
        "development_test_counts": Counter()
    }

    for i, r in enumerate(records):
        for k in ["domain", "homepage_url", "expected_label", "website_type", "label_reason", "evidence_summary", "reviewed_at", "review_method"]:
            if not r[k].strip():
                print(f"Error: Blank {k} in row {i+2}.")
                sys.exit(1)

        canon = _get_canonical_domain(r["domain"])
        
        # syntactic check
        if "." not in canon or " " in canon:
            print(f"Error: Invalid domain syntax {canon} in row {i+2}.")
            sys.exit(1)
            
        for fp in fictitious_patterns:
            if fp in canon:
                print(f"Error: Fictitious domain {canon} in row {i+2}.")
                sys.exit(1)

        if canon in domains:
            print(f"Error: Duplicate canonical domain {canon} in row {i+2}.")
            sys.exit(1)
        domains.add(canon)

        if r["expected_label"] not in allowed_labels:
            print(f"Error: Invalid label {r['expected_label']} in row {i+2}.")
            sys.exit(1)
        if r["website_type"] not in allowed_website_types:
            print(f"Error: Invalid website_type {r['website_type']} in row {i+2}.")
            sys.exit(1)
        if r["activity_status"] not in allowed_activity_statuses:
            print(f"Error: Invalid activity_status {r['activity_status']} in row {i+2}.")
            sys.exit(1)
        if r["dataset_split"] not in allowed_splits:
            print(f"Error: Invalid dataset_split {r['dataset_split']} in row {i+2}.")
            sys.exit(1)
            
        if r["review_method"] != "manual_public_web_review":
            print(f"Error: Invalid review_method {r['review_method']} in row {i+2}.")
            sys.exit(1)
            
        if len(r["label_reason"]) < 10 or len(r["evidence_summary"]) < 10:
            print(f"Error: Reason or evidence too generic in row {i+2}.")
            sys.exit(1)
            
        if not r["evidence_url_1"].strip():
            print(f"Error: Missing evidence_url_1 in row {i+2}.")
            sys.exit(1)
            
        if not r["evidence_url_1"].startswith("http"):
            print(f"Error: Invalid evidence URL scheme {r['evidence_url_1']} in row {i+2}.")
            sys.exit(1)

        if r["dataset_split"] == "development":
            dev_count += 1
            dev_labels.add(r["expected_label"])
            dev_types.add(r["website_type"])
        else:
            test_count += 1
            test_labels.add(r["expected_label"])
            test_types.add(r["website_type"])

        summary["label_counts"][r["expected_label"]] += 1
        summary["website_type_counts"][r["website_type"]] += 1
        summary["market_counts"][r["target_market"]] += 1
        summary["language_counts"][r["language"]] += 1
        summary["activity_status_counts"][r["activity_status"]] += 1
        summary["development_test_counts"][r["dataset_split"]] += 1

    if dev_count != 35:
        print(f"Error: Expected 35 development records, found {dev_count}.")
        sys.exit(1)
    if test_count != 15:
        print(f"Error: Expected 15 test records, found {test_count}.")
        sys.exit(1)

    if "gaming_media" not in dev_labels or "not_gaming_media" not in dev_labels:
        print("Error: Dev split missing positive or negative.")
        sys.exit(1)
    if "gaming_media" not in test_labels or "not_gaming_media" not in test_labels:
        print("Error: Test split missing positive or negative.")
        sys.exit(1)

    if len(test_types) <= 1:
        print("Error: Test split must contain more than one website type.")
        sys.exit(1)
    if len(dev_types) <= 1:
        print("Error: Dev split must contain more than one website type.")
        sys.exit(1)
        
    diff_types = {"game_developer", "game_publisher", "gaming_retailer", "general_media_gaming_section", "ambiguous", "inactive_or_archived_media"}
    if not any(t in diff_types for t in test_types):
        print("Error: Test split missing borderline or difficult example.")
        sys.exit(1)
    if not any(t in diff_types for t in dev_types):
        print("Error: Dev split missing borderline or difficult example.")
        sys.exit(1)

    with open("evaluation/dataset_summary.json", "w", encoding="utf-8") as f:
        json.dump({k: dict(v) if isinstance(v, Counter) else v for k, v in summary.items()}, f, indent=2)

    print("Validation successful. Summary generated.")

if __name__ == "__main__":
    validate_and_summarize()
