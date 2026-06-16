# Phase 5B Metric Consistency Audit

## Abstention Policy and Confusion Overlap (Original Code Flaw)

In the original Phase 5B report metrics (`phase5b_development_metrics.json`), abstentions **overlapped** with binary confusion matrix counts, leading to significantly skewed results—particularly for True Negatives (TN).

The original flawed implementation used the following mapping:
*   **False Negatives (Original)**: Any expected `gaming_media` that was not predicted as `gaming_media` (included `uncertain` predictions).
*   **True Negatives (Original)**: Any row NOT expected as `gaming_media` and NOT predicted as `gaming_media`. This incorrectly lumped `uncertain` predictions on negative and expected-uncertain rows into `tn`.
*   **Resulting Flaw**: `tn` inflated to 19 (because expected negative + expected uncertain rows that were predicted `uncertain` were counted as successful rejections).

## Corrected Review-Aware Binary Policy

To resolve the inconsistencies, we enforce the strict review-aware policy separating abstentions from decisions:

**Eligibility Mapping**:
*   `expected_label == "gaming_media"` -> Positive
*   `expected_label == "not_gaming_media"` -> Negative
*   `expected_label == "uncertain"` -> Excluded from binary metrics

**Prediction Mapping**:
*   `predicted_status == "verified"` -> Positive Decision
*   `predicted_status == "rejected"` -> Negative Decision
*   `predicted_status == "uncertain"` OR `"fetch_failed"` -> Abstention (Excluded from binary confusion counts)

## Corrected Headline Metrics

Applying this consistent policy to the 35 development rows:

*   **Total Rows**: 35
*   **Eligible Binary Rows**: 32 (16 Pos, 16 Neg)
*   **Total Abstentions**: 21 (7 Pos, 11 Neg, 3 Excluded)
*   **Non-abstained (Decided) Predictions**: 14 (9 Pos, 5 Neg)

**Confusion Matrix (Review-Aware)**:
*   **True Positives (TP)**: 9
*   **False Positives (FP)**: 0
*   **True Negatives (TN)**: 5
*   **False Negatives (FN among decided)**: 0

**Key Metrics**:
*   **Prediction Coverage**: 43.75% (14 decided / 32 eligible)
*   **Precision**: 100% (9 TP / 9 Total Pos Decisions)
*   **Recall (on decided)**: 100% (9 TP / 9 Total Decided Positives)
*   **Operational Recall (including abstained positives)**: 56.25% (9 TP / 16 Total Expected Positives)
*   **Strict Operational Accuracy**: 43.75% (14 correct binary decisions / 32 eligible)

## Acceptance Criteria Evaluation

Evaluating the selected threshold configuration against Phase 5B goals:
1.  **False positives <= 1**: PASS (0 FP)
2.  **Recall >= 50%**: PASS (Operational recall is 56.25%)
3.  **F1 improved over Phase 5**: PASS (Improved from 0.0 to 0.72)
4.  **Clear negative fixtures remain protected**: PASS (No clear negatives verified)
5.  **Prediction coverage >= 60%**: **FAIL** (Coverage is 43.75%)

Because prediction coverage is below the strict 60% requirement under the consistent review-aware policy, **Phase 5B acceptance criteria are NOT fully met.** Execution of the protected test set (Phase 6) has been halted.
