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
- Strict Accuracy: 11.43%
- Precision: 0.00%
- Recall: 0.00%
- F1 Score: 0.00%
- Coverage: 15.62%

## Test Metrics
- Strict Accuracy: 40.00%
- Precision: 0.00%
- Recall: 0.00%
- F1 Score: 0.00%
- Coverage: 0.00%

## Overall Metrics
- Strict Accuracy: 20.00%
- Precision: 0.00%
- Recall: 0.00%
- F1 Score: 0.00%
- Coverage: 12.20%

## Abstention and Fetch-Failure Counts
Total Fetch Failed: 44
Total Uncertain: 1

## Statement
No verifier changes were made. This is purely a baseline measurement.
