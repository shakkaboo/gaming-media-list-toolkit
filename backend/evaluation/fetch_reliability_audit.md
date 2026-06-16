# Fetch Reliability Audit

## 1. Overview
The baseline `FetchService` and its `page_fetcher.py` was built with strong SSRF protection in mind (`DNSResolver`) but failed to adapt to real-world edge cases when fetching gaming media domains. This audit covers the state prior to Phase 4A improvements.

## 2. HTTP Architecture
- **Library**: `httpx.AsyncClient`
- **Concurrency**: Bounded by global and host-specific semaphores.
- **Redirection**: Manual loop intercepting HTTP 301, 302, 303, 307, 308 to re-run DNS SSRF safety checks.
- **Timeout**: Strict settings for connect, read, write, and pool timeouts.

## 3. Findings
1. **Redirect Loops**: The manual redirect loop incorrectly normalized intermediate URLs by stripping trailing slashes before adding them to `visited_urls`, resulting in 32 false positive loop detections for domains redirecting to their canonical trailing-slash versions.
2. **Missing Headers**: `Accept-Language` was not provided, causing issues with multilingual or strictly configured servers.
3. **Budget and Retry Tracking**: Retries and redirects were loosely tracked but not holistically capped against a per-domain budget in a way that permitted safe fallback mechanisms.
4. **Lack of Fallbacks**: Pages utilizing JavaScript shells (e.g., SPAs) or Cloudflare challenge pages returned HTTP 200/403 but provided no useful text, and the system had no capability to bypass them or find alternate RSS/Sitemap evidence.

## 4. Phase 4A Upgrades
- The new `FetchOrchestrator` implements strict budget tracking (max 5 standard HTTP requests, max 1 browser request).
- Structured `AcquisitionResult` replaces simple `FetchedPage` for evaluation.
- Playwright, Sitemap, and RSS fallbacks are engaged based on precise `failure_category` conditions.