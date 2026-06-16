# Phase 3 vs Phase 4A vs Phase 4B Comparison

This document tracks the progression of the Gaming Media List Toolkit's reliability evaluation through the first three testing phases.

## Phase 3 (Baseline)

In Phase 3, we evaluated the production classifier as-is, using the legacy `fetch_page_with_retries` acquisition path.

* **Fetch Success Rate**: 12% (6 of 50 domains fetched successfully).
* **Failure Cause**: The simple HTTP client was immediately blocked by Cloudflare, Imperva, and other basic bot-protection mechanisms. 44 of 50 domains failed to return usable HTML.
* **Classification Performance**: Due to the near-total lack of acquired evidence, the classifier abstained ("fetch_failed") on the vast majority of domains.

## Phase 4A (Acquisition Improvements)

In Phase 4A, we introduced the `FetchOrchestrator` to improve evidence acquisition without altering the downstream classifier. This orchestrator added canonical fallbacks, sitemap discovery, and Playwright rendering.

* **Acquisition Success Rate**: 58% (29 of 50 domains returned usable evidence).
* **Impact**: The system successfully bypassed basic bot blocks for many sites, yielding parseable HTML for the classifier to analyze.

## Phase 4B (Re-classification)

In Phase 4B, we re-ran the *unmodified Phase 3 classifier* using the improved evidence from Phase 4A. The goal was to isolate the impact of acquisition improvements on final classification outcomes.

### Metric Definitions
For this binary classification evaluation, we map the multi-class labels as follows:
* **True Positive (TP)**: Expected `gaming_media`, Predicted `verified`
* **False Positive (FP)**: Expected `not_gaming_media` or `uncertain`, Predicted `verified`
* **True Negative (TN)**: Expected `not_gaming_media` or `uncertain`, Predicted `rejected` or `uncertain`
* **False Negative (FN)**: Expected `gaming_media`, Predicted `rejected` or `uncertain`

### Results

* **Total Domains**: 50
* **Expected Positives (`gaming_media`)**: 20
* **Expected Negatives (`not_gaming_media` + `uncertain`)**: 30

| Metric | Count / Value |
| :--- | :--- |
| True Positives (TP) | 2 |
| False Positives (FP) | 1 |
| True Negatives (TN) | 29 |
| False Negatives (FN) | 18 |

### Performance Metrics

* **Precision**: 66.7% (2 / 3)
* **Recall**: 10.0% (2 / 20)
* **F1 Score**: 17.4%
* **Accuracy** (Binary Match): 62% (31 / 50)

### Conclusion

While Phase 4A dramatically improved our ability to *acquire* HTML, the unmodified Phase 3 classifier ruleset remains heavily restrictive. Even with successful HTML acquisition, the classifier only verified 2 out of 20 legitimate gaming publications. 

The primary cause of failure is no longer network acquisition, but rather the strict rule thresholds (e.g., minimum scores of 18 for both gaming and editorial components) and the lack of robust language/market support. This confirms that Phase 5 (Scoring Redesign) is necessary to achieve acceptable recall.
