# Baseline Execution Path

This document traces the exact verification path in the current production MVP before any reliability improvements.

**1. Entry Function:**
`VerificationService.verify_candidates` takes a `VerificationRequest` which contains candidate URLs. It restricts concurrency and respects limits.

**2. HTML Fetch Path:**
`FetchService.fetch_pages(fetch_req)` is called to retrieve the live HTML for the candidate URLs via HTTP requests, applying basic timeouts, a common User-Agent, and following redirects. It returns `FetchedPage` objects.

**3. Fetch-Failure Path:**
If `page.success` is False, `VerificationService._verify_page_sync` short-circuits and immediately returns a `VerificationResult` with status `fetch_failed` and a score of 0, bypassing HTML analysis and classification completely.

**4. Analyzer Function:**
If fetched successfully, `HtmlAnalyzer(html).analyze()` extracts raw signals from the page structure, returning `ExtractedSiteSignals` containing text lengths, tags, links, meta information, and market evidence (e.g. language/location tags).

**5. Classifier Function:**
`Classifier.classify` is invoked with the URL, domain, and `ExtractedSiteSignals`. It routes the signals into rule-based scoring components.

**6. Component Score Functions:**
Inside `Classifier.classify`, the signals are passed sequentially to these functions in `app.verification.rules`:
- `evaluate_gaming_relevance`: Assigns points (0-40) based on gaming terminology and keywords in title, description, and body.
- `evaluate_editorial_structure`: Assigns points (0-40) based on article patterns, navigation links, and structural signals.
- `evaluate_activity`: Assigns points (0-20) based on the recency of detected publication dates.
- `evaluate_publication_identity`: Assigns points (0-15) based on explicit "about us", "staff", or author bylines.
- `evaluate_negative_penalties`: Deducts points (-100 to 0) if storefront patterns (cart, buy), publisher patterns, or irrelevant domains are detected.

**7. Result Model:**
The components return scores and lists of `VerificationReason` objects.
The raw score is calculated as: `gaming + editorial + activity + identity - penalty`.
The bounded score is constrained between 0 and 100.

**8. Final Threshold Logic:**
A hard rejection occurs if the `bounded_score < 50`.
Another hard rejection occurs if `negative_penalty >= 40` and `editorial_structure_score < 18`.
Otherwise, it uses threshold checks:
- `verified` if bounded score >= 70 (default) and minimum gaming (18) and editorial (18) scores are met.
- `rejected` if bounded score < 40 (default).
- `uncertain` if falling in between, or if the score is >= 70 but the minimum component thresholds are missed.

**9. Status Values:**
The possible returned statuses are `verified`, `rejected`, `uncertain`, and `fetch_failed`.
