# Baseline Metric Policy

This document defines how predictions made by the verifier are mapped and scored against the evaluation dataset expected labels.

## Expected Labels
The dataset contains three manual labels:
- `gaming_media` (Positive)
- `not_gaming_media` (Negative)
- `uncertain` (Ambiguous or impossible to confirm)

## Verifier Statuses
The verifier predicts one of four statuses:
- `verified`
- `rejected`
- `uncertain`
- `fetch_failed`

## Primary Status Mapping
Predictions are mapped to labels as follows:
- `verified` -> `gaming_media`
- `rejected` -> `not_gaming_media`
- `uncertain` -> `uncertain`
- `fetch_failed` -> `uncertain` (for review-aware analysis), but scored as an incorrect prediction under strict scoring unless the expected label was also `uncertain`.
Note: `fetch_failed` is not silently mapped to `not_gaming_media`, because an inability to fetch (e.g. Cloudflare block) is not affirmative proof that the site is not gaming media.

## Strict Evaluation Policy
A prediction is considered correct only if there is an exact match:
- predicted `verified` matches expected `gaming_media`
- predicted `rejected` matches expected `not_gaming_media`
- predicted `uncertain` matches expected `uncertain`

A `fetch_failed` prediction is strictly incorrect unless the expected label was `uncertain`.

## Review-Aware Binary Policy
For standard binary metrics (Precision, Recall, F1, Specificity):
1. **Eligible Rows**: Exclude any row where `expected_label == uncertain`. These represent fundamentally ambiguous or blocked sites where even a human reviewer cannot make a binary decision.
2. **Positives and Negatives**:
   - `gaming_media` = Positive
   - `not_gaming_media` = Negative
3. **Abstentions**:
   - Predicted `uncertain` and predicted `fetch_failed` are treated as **abstentions**.
   - Abstentions are not treated as true negatives or false negatives in the core binary metric calculation. Instead, they reduce the "prediction coverage".
4. **Calculations**:
   - Precision = TP / (TP + FP)
   - Recall = TP / (TP + FN)
   - Specificity = TN / (TN + FP)
   - Coverage = (TP + FP + TN + FN) / Eligible Rows

This policy allows the evaluator to measure how accurately the verifier performs when it actually makes a decision, while penalizing it via coverage when it abstains.
