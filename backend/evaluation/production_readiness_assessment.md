# Production Readiness Assessment — v2 Multilingual Classifier
**Date**: 2026-06-17  
**Classifier**: `v2_multilingual_explainable`  
**Evaluated against**: Phase 6 protected test (15 rows, one-time, locked)

---

## Decision Summary

| Decision | Outcome | Rationale |
|---|---|---|
| v2 approved as autonomous production default | **NO** | Coverage 44.4%, specificity 0%, publisher false positive unresolved |
| v2 approved for shadow mode | **YES** | Precision 75%, F1 0.857, gate prevents incorrect decided verdicts |
| v2 approved for human-assisted review | **YES** | All decided verdicts were either correct positives or one identifiable FP |
| Baseline remains production default | **YES** | No evidence v2 meets the bar for autonomous replacement |
| Future tuning permitted on this test set | **NO** | Test set is locked; any tuning contaminates its validity |

---

## Criteria and Outcomes

### Criterion 1: Decision Coverage ≥ 70%
**Result: 44.4% — FAIL**

The evidence-safety gate deferred 10 of 15 rows. The classifier did not issue a verdict for sites that use JavaScript rendering or have pages the acquisition path cannot read. This coverage level is insufficient for an autonomous production role.

### Criterion 2: Precision ≥ 70%
**Result: 75.0% — PASS**

Three of four decided positive verdicts were correct. The one false positive (ea.com) is an identifiable structural pattern (publisher content) that a future hard-rejection rule can address.

### Criterion 3: Operational Recall ≥ 70%
**Result: 75.0% — PASS**

Three of four confirmed gaming media sites in the binary-eligible set were correctly verified. One (kotaku.com) abstained due to evidence unavailability.

### Criterion 4: Specificity > 0%
**Result: 0.0% — FAIL**

All confirmed-negative rows abstained. The classifier never issued an active rejection verdict in the protected test. This prevents assessing its ability to correctly reject non-media sites autonomously.

### Criterion 5: No post-freeze tuning
**Result: CONFIRMED — PASS**

The lock file was written at completion (2026-06-16T20:37:34 UTC). No classifier source, threshold, vocabulary, or evidence-gate parameter was changed after Phase 5D was frozen. The scoring-rule hash in the runner verified this at evaluation time.

### Criterion 6: Benchmark dataset integrity
**Result: CONFIRMED — PASS**

Dataset SHA-256: `ab160badfdcf2b478450006ae168b020f0aead9194875a579937884f7c2830aa`  
This hash matches the expected value recorded in both the runner and the lock file.

---

## Known Defects to Address Before Production Promotion

### DEF-001: Publisher False Positive (ea.com)
- **Severity**: Medium
- **Description**: EA.com scored 69 (above the verified threshold of 58). The site contains heavy gaming content vocabulary but is a game publisher, not editorial gaming media.
- **Proposed fix**: Extend the `game_developer_corporate_site` or add a `game_publisher_corporate_site` hard-rejection rule triggered by investor-relations, corporate-careers, or game-portfolio structural signals combined with absence of editorial navigation.
- **Requirement**: Re-evaluate on new data; do not re-use the Phase 6 test set.

### DEF-002: Low Evidence Yield on JavaScript-Rendered Sites
- **Severity**: High (coverage impact)
- **Description**: 10/15 test rows produced no usable evidence. Sites including kotaku.com, yodobashi.com, and gamestop.ca appear to serve JavaScript shells to the acquisition path.
- **Proposed fix**: Add a headless-browser or pre-rendered CDN fallback acquisition path. Alternatively, incorporate RSS/Atom feed evidence as a primary source for editorial sites.
- **Requirement**: Addressed before re-evaluation; test with new data.

### DEF-003: Zero Specificity on Negative Class
- **Severity**: Medium
- **Description**: No confirmed-negative site received an active "rejected" verdict. All abstained. The classifier cannot currently demonstrate it can autonomously reject non-gaming-media sites.
- **Proposed fix**: Ensure negative-class sites have sufficient evidence yield (addresses DEF-002). If evidence remains low, consider a separate fallback heuristic for known-negative structural patterns.
- **Requirement**: Addressed before autonomous production promotion.

---

## Shadow Mode Approval

The `v2_shadow` classifier mode is approved for immediate deployment:

- The **baseline** classifier issues the production verdict.
- v2 runs in parallel and its output is attached as `v2_shadow` on the baseline `VerificationResult`.
- Human reviewers can inspect v2's component scores, decision reason, gate override, and `review_recommendation` before acting.
- No production verdict is changed by the shadow attachment.

Shadow mode is the **recommended path** for gaining operational confidence before a future autonomous promotion decision.

---

## Future Promotion Path

Promotion of v2 to autonomous production default requires:

1. Address DEF-001, DEF-002, DEF-003.
2. Collect new labelled data (minimum 50 rows; 20+ negatives).
3. Run a fresh development calibration cycle.
4. **Reserve a new, untouched test set** — do not reuse the Phase 6 rows.
5. Achieve coverage ≥ 70%, precision ≥ 80%, specificity > 0% on the new test set.
6. Complete a new protection lock.

The Phase 6 test set is permanently retired for evaluation purposes.
