# Current Verifier Mapping to Guidelines

| Evaluation concept | Existing implementation |
| --- | --- |
| Gaming relevance | `evaluate_gaming_relevance`, score (0-35) |
| Editorial/media evidence | `evaluate_editorial_structure`, score (0-35) |
| Activity | `evaluate_activity`, score (0-15) and status (`active_recently`, `possibly_active`, `stale`) |
| Publication identity | `evaluate_publication_identity`, score (0-15) |
| Negative evidence | `evaluate_negative_penalties`, penalty (0-80) |
| Market relevance | Not scored. Language is detected and exported via `market_evidence` |
| Technical confidence | Explicitly calculated via separate logic resulting in a `confidence` field (0.0 - 1.0) based on sub-score agreement and evidence |
| Hard rejection | Explicitly implemented (e.g. Cloudflare challenges result in `uncertain`/score 0, parked domains result in `rejected`/score 0, high penalties coupled with low editorial score result in `rejected`) |
| Final thresholds | Verified threshold defaults to 70 (also requiring gaming_score >= 18 and editorial_score >= 18). Uncertain threshold defaults to 40. |
| Explainability | Reasons and matched evidence are fully persisted in `positive_reasons` and `negative_reasons` |

### Important Answers

**Is market relevance explicitly scored?**
No, it is captured in `market_evidence` (e.g. `lang=en`) but not scored.

**Is technical confidence a separate score?**
Yes, the `confidence` variable is calculated separately ranging from 0.0 to 1.0.

**Are negative penalties capped?**
Yes, `evaluate_negative_penalties` caps the total penalty at 80 (`min(80, penalty)`).

**Can a store pass with a high gaming score?**
A store could theoretically pass if the raw score stays above 70 and minimum gaming (18) and editorial (18) are met. However, there is a hard rejection rule for penalty >= 40 AND editorial_score < 18, which rejects it regardless. 

**Can a fetch failure only produce rejected, or is there an uncertain path?**
Fetch failure automatically assigns `fetch_failed` status, which is not `uncertain`. It is essentially a rejection with score 0 and confidence 0.

**Are hard rejection rules distinct from penalties?**
Yes, there are specific hard-coded logic branches for Cloudflare challenges, parked domains, and fetch failures.

**Are component scores exposed through the API?**
Yes, `gaming_relevance_score`, `editorial_structure_score`, `activity_score`, `publication_identity_score`, `negative_penalty` are fields on `VerificationResult`.

**Are decision reasons persisted?**
Yes, through `positive_reasons` and `negative_reasons`.
