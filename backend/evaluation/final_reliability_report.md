# Final Reliability Report — Gaming Media Verification Classifier
**Branch**: reliability-evaluation  
**Report date**: 2026-06-17  
**Author**: automated (Phase 7 final integration)

---

## 1. Overview

This report summarises the complete multi-phase classifier development and evaluation programme, covering Phases 1–6. It separates current production behaviour (baseline classifier) from experimental v2 behaviour, and provides the definitive record of the single protected test evaluation that concluded Phase 6.

No scoring rules, thresholds, vocabulary, evidence gate, labels, traffic logic, or acquisition budget have been modified since Phase 5D was frozen.

---

## 2. Classifier Versions

| Identifier | Status | Description |
|---|---|---|
| `baseline` | **Production default** | Offline rule-based scoring of homepage HTML. No evidence gate. Deterministic. |
| `v2_multilingual_explainable` | Experimental (shadow/review) | Multilingual scoring (EN/JA/FR) + evidence-safety gate. Requires usable HTML to issue a decided verdict. |
| `v2_shadow` | **New in Phase 7** | Runs baseline as the production decision; runs v2 in parallel and attaches shadow output for human review. |

---

## 3. Configuration Freeze (Phase 5D)

The following configuration was frozen before the protected test and must not be changed without starting a new evaluation cycle:

| Parameter | Value |
|---|---|
| `verified_threshold` | 58 |
| `uncertain_threshold` | 40 |
| `gaming_minimum` | 14 |
| `media_minimum` | 10 |
| `technical_minimum` | 0 |
| `market_minimum` | 0 |
| `evidence_safety_gate` | enabled |

Configuration hash (SHA-256): `71d69a2c454928b4ea7e1f1e1c0ff5c98e5bd461b6b8f9050f7312118040e9bf`  
Dataset hash (SHA-256): `ab160badfdcf2b478450006ae168b020f0aead9194875a579937884f7c2830aa`

---

## 4. Development Metrics (Phase 5C — 35 rows, **not** the protected set)

Development results are shown for transparency. They informed threshold calibration and must not be used to re-tune the frozen configuration.

> Development metrics are stored in `backend/evaluation/results/phase5c_development_metrics.json`. Refer to that file for the authoritative development numbers.

Key development signals that led to the freeze:
- Evidence-gate significantly reduced false positives at the cost of higher abstention.
- Score distribution showed clear separation between gaming media and retailers/developers above the verified threshold.

---

## 5. Protected Test Metrics (Phase 6 — 15 rows, one-time run)

**Lock file**: `backend/evaluation/results/phase6_protected_test.lock.json`  
**Completed**: 2026-06-16T20:37:34 UTC  
**Runner**: `phase6_v1`  
**Post-freeze tuning**: NONE

### 5.1 Transport and Evidence

| Metric | Value |
|---|---|
| Total test rows | 15 |
| Transport successes | 15 / 15 |
| Usable evidence obtained | 5 / 15 |
| Evidence-gate overrides (insufficient evidence) | 4 |
| Rows abstained | 10 |

### 5.2 Prediction Distribution

| Outcome | Count |
|---|---|
| Verified | 5 |
| Rejected | 0 |
| Uncertain | 10 |
| Fetch failed | 0 |

### 5.3 Binary Classification Metrics

Binary metrics are computed over the 9 rows with a non-uncertain expected label (`confirmed` market status).

| Metric | Value |
|---|---|
| Eligible binary rows | 9 |
| True positives (TP) | 3 |
| False positives (FP) | **1** |
| True negatives decided (TN) | 0 |
| False negatives decided (FN) | 0 |
| Abstentions | 5 |
| Decision coverage | **44.4%** |
| Precision | **75.0%** |
| Decided-prediction recall | 100.0% |
| Operational positive recall | **75.0%** |
| F1 | **0.857** |
| Specificity | **0.0%** |
| Strict accuracy | **53.3%** |
| Relevance-label accuracy | 75.0% |

### 5.4 Market Status Distribution (15 rows)

| Status | Count |
|---|---|
| confirmed | 9 |
| unconfirmed | 6 |

---

## 6. Error Analysis

### 6.1 False Positives (1)

| Domain | Score | Reason |
|---|---|---|
| **ea.com** | 69 | Score meets verified threshold. EA is a game publisher, not gaming media. The scorer conflates gaming-related content with gaming editorial media. |

### 6.2 False Negatives among Decided Predictions (0)

None. Every prediction that issued a verdict was correct among positives.

### 6.3 Abstained Expected Positives (operational false negative, 1)

| Domain | Score | Reason |
|---|---|---|
| **kotaku.com** | 57 | Score fell in uncertain range (40–58). No usable evidence was acquired; the evidence gate withheld a decision. |

### 6.4 Abstained Expected Negatives (4)

nintendo.co.jp, yodobashi.com, gamestop.ca, thescoreesports.com — all abstained because usable evidence was not acquired. None produced an incorrect positive verdict.

### 6.5 Evidence-Gate Overrides (4)

These domains had scores calculated but were blocked by the insufficient-evidence gate:

| Domain | Score |
|---|---|
| itmedia.co.jp | 26 |
| nintendo.co.jp | 5 |
| thescoreesports.com | 32 |
| dmm.com | 18 |

The gate prevented potentially incorrect low-confidence decisions from reaching a verdict.

---

## 7. Current Production Behaviour (Baseline)

- Classifier: `baseline`
- All homepage HTML is scored deterministically offline.
- No evidence gate; every candidate receives a verdict.
- Thresholds: verified ≥ 70, uncertain 40–69 (settings defaults; may be overridden per-request).
- Produces `VerificationResult` with `verification_status` ∈ {verified, uncertain, rejected, fetch_failed}.
- No multilingual scoring; English-centric vocabulary.

**The baseline is not modified by this programme.** All Phase 5–6 work is additive.

---

## 8. v2 Experimental Behaviour

- Classifier: `v2_multilingual_explainable`
- Multilingual vocabulary (English, Japanese, French).
- Five component scores: gaming, media, market, activity, technical.
- Contextual deductions for publisher/developer/retailer signals.
- Evidence-safety gate: no decided verdict without usable HTML evidence.
- Produces `VerificationResultV2` with `predicted_status` ∈ {verified, rejected, uncertain}.

**v2 is not the production default and must not be promoted autonomously.**

---

## 9. Shadow Mode (Phase 7, New)

Requesting `classifier_version = "v2_shadow"` activates shadow mode:

1. The **baseline** classifier runs and its result is the production decision.
2. The **v2** classifier also runs on the same acquisition.
3. The baseline `VerificationResult` is returned, with a `v2_shadow` field containing:
   - v2 predicted status, relevance label, market status
   - All five component scores plus deductions and total score
   - Hard-rejection rule and evidence
   - Evidence-gate override reason
   - v2 explanation (decision reason)
   - `review_recommendation` ∈ {agree, v2_abstained, review_v2_positive, review_v2_negative, review}
4. The production decision is **always the baseline result**.

This allows human reviewers to compare baseline verdicts against v2 signals without changing production output.

---

## 10. Limitations

| Limitation | Detail |
|---|---|
| Low decision coverage | 44.4% on protected test. 10/15 rows produced no verdict due to evidence-gate. Particularly affects non-English and JavaScript-heavy sites. |
| Zero specificity | All confirmed-negative rows in the test set abstained. The gate prevented false positives but also prevented any true negative decisions. |
| ea.com false positive | Score 69 met the verified threshold. Game publishers score highly on gaming vocabulary. A hard-rejection rule for dominant publisher signals could fix this but has not been added. |
| kotaku.com operational miss | Score 57 fell below the verified threshold with no usable evidence. The site appears to use JavaScript rendering that was not served to the acquisition path. |
| Small test set | 15 rows. All metrics carry wide confidence intervals. |
| English-language bias remains | Despite multilingual vocabulary, Japanese and French sites showed lower evidence yield. |

---

## 11. Future Improvements

The following improvements are scoped for a future evaluation cycle. They require new labelled data and a fresh, untouched test set.

1. **Publisher hard-rejection rule** — explicitly reject sites whose structural signals indicate a game developer or publisher corporate site, even when gaming content score is high.
2. **JavaScript-rendered page fallback** — acquire evidence for sites that return JavaScript shells via a headless browser or pre-rendered CDN path.
3. **Larger test set** — expand from 15 to ≥50 rows to reduce statistical uncertainty, especially for the negative class.
4. **Specificity calibration** — tune the threshold or evidence-gate sensitivity to allow decided negative verdicts.
5. **Market evidence expansion** — improve Japanese and French market evidence signals to reduce abstention on non-English sites.

---

## 12. Artifact Registry

| Artifact | Path | Notes |
|---|---|---|
| Phase 6 lock | `evaluation/results/phase6_protected_test.lock.json` | SHA-sealed, do not modify |
| Phase 6 predictions | `evaluation/results/phase6_test_predictions.csv` | Hash-sealed |
| Phase 6 metrics | `evaluation/results/phase6_test_metrics.json` | Hash-sealed |
| Phase 6 error analysis | `evaluation/results/phase6_test_error_analysis.md` | |
| Phase 6 comparison | `evaluation/results/phase6_baseline_vs_v2_comparison.md` | |
| Phase 6 report | `evaluation/results/phase6_test_report.md` | |
| Frozen configuration | `evaluation/phase5d_frozen_configuration.json` | Defines thresholds, gates |
| Benchmark dataset | `evaluation/gaming_media_evaluation.csv` | SHA-sealed |
| Final summary | `evaluation/phase6_final_summary.json` | Machine-readable |
| This report | `evaluation/final_reliability_report.md` | |
| Supervisor response | `evaluation/final_supervisor_response.md` | |
| Readiness assessment | `evaluation/production_readiness_assessment.md` | |
