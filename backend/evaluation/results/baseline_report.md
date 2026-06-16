# Baseline Evaluation Report

A controlled baseline measurement on a small manually reviewed MVP benchmark.

## 1. Purpose
Measure current verifier exactly as it exists before reliability improvements.

## 2. Dataset Composition
50 real websites manually reviewed. 35 dev, 15 test.

## 3. Metric Policy
Strict correctness requires exact matches. Binary metrics exclude `uncertain` expected labels. `fetch_failed` and `uncertain` predictions are counted as abstentions and reduce coverage.

## 4. Current Verifier Architecture
Rules-based heuristic combining gaming, editorial, activity, and identity scores minus a negative penalty.

## Development Metrics
- Strict Accuracy: 45.71%
- Precision: 50.00%
- Recall: 100.00%
- F1 Score: 66.67%
- Coverage: 100.00%

## Test Metrics
- Strict Accuracy: 26.67%
- Precision: 44.44%
- Recall: 100.00%
- F1 Score: 61.54%
- Coverage: 100.00%

## Overall Metrics
- Strict Accuracy: 40.00%
- Precision: 48.78%
- Recall: 100.00%
- F1 Score: 65.57%
- Coverage: 100.00%

## Abstention and Fetch-Failure Counts
Total Fetch Failed: 0
Total Uncertain: 0

## Statement
No verifier changes were made. This is purely a baseline measurement.
