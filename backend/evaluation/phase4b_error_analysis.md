# Phase 4B Error Analysis

This document analyzes the domain-level classification failures encountered when running the unmodified Phase 3 classifier on the improved Phase 4A acquired evidence.

## Summary of Correct Classifications

Assuming `gaming_media` maps to `verified`, `not_gaming_media` maps to `rejected`, and `uncertain` is treated as a negative prediction that should be `rejected`:

* **Correctly Verified (True Positives)**: 2 domains (`cgmagonline.com`, `rockpapershotgun.com`)
* **Correctly Rejected (True Negatives)**: 29 domains (all 20 `not_gaming_media` domains, plus 9 `uncertain` domains)
* **Total Correct Labels**: 31 out of 50 (62% Accuracy)

## Analysis of Failures

The classifier failed to produce the expected label for 19 domains.

### Group 1: Fetch Failures

For these domains, the acquisition path (even with Playwright and sitemap fallbacks) failed to yield usable evidence. As a result, the classifier correctly returned a 0 score and abstained/rejected.

* **`automaton-media.com`**: Expected `gaming_media`, Predicted `rejected` (Score: 0). Cause: Fetch failure.
* **`canadiangamingnews.com`**: Expected `gaming_media`, Predicted `rejected` (Score: 0). Cause: Fetch failure.
* **`gamecanucks.com`**: Expected `gaming_media`, Predicted `rejected` (Score: 0). Cause: Fetch failure.
* **`canadianonlinegamers.com`**: Expected `gaming_media`, Predicted `rejected` (Score: 0). Cause: Fetch failure.
* **`gamespot.com`**: Expected `gaming_media`, Predicted `rejected` (Score: 0). Cause: Fetch failure (likely strong bot protection).

### Group 2: Insufficient Total Score (Missed Verified Threshold)

These domains successfully returned usable HTML and accumulated enough points to trigger the `uncertain` status (>40 points), but failed to reach the `verified` threshold (70 points).

* **`gematsu.com`**: Expected `gaming_media`, Predicted `uncertain` (Score: 63). Cause: Scored high, but missed 70.
* **`destructoid.com`**: Expected `gaming_media`, Predicted `uncertain` (Score: 65). Cause: Scored high, but missed 70.
* **`kotaku.com`**: Expected `gaming_media`, Predicted `uncertain` (Score: 56). Cause: Missed 70.
* **`pcgamer.com`**: Expected `gaming_media`, Predicted `uncertain` (Score: 54). Cause: Missed 70.
* **`polygon.com`**: Expected `gaming_media`, Predicted `uncertain` (Score: 49). Cause: Missed 70.
* **`thegamer.com`**: Expected `gaming_media`, Predicted `uncertain` (Score: 44). Cause: Missed 70.
* **`gamespark.jp`**: Expected `gaming_media`, Predicted `uncertain` (Score: 52). Cause: Missed 70 (Language barrier likely suppressed score).
* **`inside-games.jp`**: Expected `gaming_media`, Predicted `uncertain` (Score: 52). Cause: Missed 70 (Language barrier likely suppressed score).

*Analysis*: The classifier rules are heavily reliant on English keywords. These domains are massive, legitimate gaming publications, yet the rules failed to confidently verify them.

### Group 3: Extreme Under-Scoring (Missed Uncertain Threshold)

These domains were successfully fetched but failed to reach even the minimum 40-point `uncertain` threshold, resulting in a hard rejection.

* **`famitsu.com`**: Expected `gaming_media`, Predicted `rejected` (Score: 37). Cause: Japanese language content evaded English keyword matching.
* **`dengekionline.com`**: Expected `gaming_media`, Predicted `rejected` (Score: 37). Cause: Japanese language content evaded English keyword matching.
* **`ign.com`**: Expected `gaming_media`, Predicted `rejected` (Score: 22). Cause: Likely penalized heavily by e-commerce/store keywords (e.g., IGN Store) and JS-heavy rendering preventing deep textual analysis.
* **`4gamer.net`**: Expected `gaming_media`, Predicted `rejected` (Score: 19). Cause: Japanese language.
* **`jp.ign.com`**: Expected `gaming_media`, Predicted `rejected` (Score: 17). Cause: Japanese language.

*Analysis*: The lack of internationalization support is the primary driver of failure here. The presence of store/e-commerce links heavily penalizes large media conglomerates like IGN.

### Group 4: False Positives (Over-Scoring)

This domain was verified as a gaming publication despite being labelled as uncertain (it is a general tech/culture publication that covers gaming).

* **`theverge.com`**: Expected `uncertain`, Predicted `verified` (Score: 77). Cause: The Verge publishes enough gaming and editorial content to easily trip the keyword sensors and surpass the 70-point threshold, exposing the lack of nuanced context evaluation in the strict rule-based system.
