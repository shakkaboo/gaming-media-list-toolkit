# Baseline Fetch Failure Analysis

## Summary
Out of 50 domains in the Phase 2 benchmark, 44 failed to fetch correctly using the standard HTTP path during the baseline evaluation. The vast majority of these were caused by improper handling of HTTP to HTTPS redirects and trailing slashes, resulting in `redirect_loop` failures.

## Breakdown of Failures

- **redirect_loop**: 32
- **http_client_error**: 6
- **dns_failed**: 3
- **timeout**: 2
- **unexpected_fetch_error**: 1

### Redirect Loops
The baseline `_fetch_attempt` loop maintained a `visited_urls` set but checked the normalized URL against it. A server redirecting from `http://domain.com` to `https://domain.com/` resulted in the latter being normalized back to `https://domain.com`, which the client mistakenly identified as a redirect loop. 

### HTTP Client Errors (401, 403, 404)
Some sites actively blocked the baseline `User-Agent` ("GamingMediaDiscoveryBot/0.1") or required proper `Accept-Language` headers. Some returned 403 Forbidden due to Cloudflare challenge pages, which were not correctly categorized.

### DNS Failures
A few domains failed DNS resolution due to timeouts or temporary issues.

### Timeouts
Strict 5-second connect and 10-second read timeouts caused 2 sites to fail.

## Phase 4A Resolution Path
- **Redirects**: Fixed the manual loop to check un-normalized URLs while retaining DNS SSRF safety.
- **Headers**: Added standard `Accept` and `Accept-Language` headers.
- **Fallbacks**: Introduced Playwright, Sitemap, and RSS fallbacks to recover from Challenge pages, JS shells, and 403s.