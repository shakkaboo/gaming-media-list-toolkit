# Phase 4B Execution Path

This document outlines the evidence acquisition and classification pipeline, demonstrating that the classifier receives its inputs through the exact same unchanged production integration path, despite the underlying acquisition improvements.

## Phase 3 Execution Path (Old)

1. **Request**: `VerificationService.verify_candidates()` receives a batch of URLs.
2. **Fetch**: `FetchService.fetch_pages()` was called. It iterated over the URLs and directly invoked `fetch_page_with_retries()`, fetching only the canonical homepage.
3. **Result**: A flat list of `FetchedPage` objects was returned to `VerificationService`.
4. **Analysis**: For each `FetchedPage`, `VerificationService` instantiated `HtmlAnalyzer(html)` to produce an `ExtractedSiteSignals` object.
5. **Classification**: The `ExtractedSiteSignals` object was passed to `Classifier.classify()`, which output a `VerificationResult`.

## Phase 4B Execution Path (New)

1. **Request**: The evaluator (or application via `VerificationService.verify_candidates()`) requests evidence for a batch of URLs.
2. **Acquisition**: `FetchService` now calls `acquire_evidence_batch()`, which delegates to the `FetchOrchestrator`.
3. **Orchestration**: `FetchOrchestrator` uses canonical fallbacks, Playwright rendering, and RSS/Sitemap discovery. It returns an `AcquisitionResult` containing a `primary_page` and potentially multiple `supporting_pages` (which are just instances of `FetchedPage`).
4. **Backward Compatibility**: When called via `FetchService.fetch_pages()`, the `AcquisitionResult` is flattened into a standard list of `FetchedPage` objects.
5. **Analysis**: For each `FetchedPage` in the returned evidence, the `HtmlAnalyzer(html)` is instantiated exactly as before, producing an `ExtractedSiteSignals` object.
6. **Classification**: The `ExtractedSiteSignals` object is passed to the unmodified `Classifier.classify()`. The highest scoring classification for a domain across its fetched pages represents the domain's ultimate classification.

## Proof of Integration Immutability

* **Unchanged Data Structures**: The input to the analyzer remains the unmodified `FetchedPage` model. The output remains `ExtractedSiteSignals`.
* **Unchanged Pipeline**: The `HtmlAnalyzer` and `Classifier` classes were not modified to handle the new `AcquisitionResult`. They are completely unaware of whether a page was acquired via a simple HTTP GET, a Playwright render, or discovered via a sitemap.
* **Unchanged Dependencies**: `VerificationService._verify_page_sync` still uses the exact same `analyzer = HtmlAnalyzer(html)` and `self.classifier.classify(...)` calls.

By decoupling the *acquisition* (how we get the HTML) from the *classification* (how we score the HTML), we ensure the evaluation cleanly isolates the impact of evidence quality without risking classifier regression.
