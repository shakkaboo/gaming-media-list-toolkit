# Dataset Review Audit

**Domains Removed and Why**
- `example-jp-blocked.jp`: Fictitious reserved domain, removed to replace with a real blocked/difficult Japanese domain.
- `dead-gaming-site-blocked.com`: Fictitious synthetic domain, removed to replace with a real blocked/difficult global domain.
- `oldcanadiangaming.ca`: Fictitious/placeholder domain, removed to replace with a real archived/inactive domain.
- `luminanews.ca`: Fictitious/placeholder domain, removed.

**Replacement Real Domains**
- `gamewith.jp` (Japan, ambiguous/publication)
- `dmm.com` (Japan, ambiguous/publisher, geoblocks)
- `vr-zone.com` (Global, archived/inactive)
- `1up.com` (Global, archived/inactive, redirects)

**Labels Changed and Why**
- `news.yahoo.co.jp`: Reassessed from `uncertain` to `uncertain` but explicitly noted as aggregated rather than originally authored.
- `theverge.com`: Reassessed from `not_gaming_media` to `uncertain` due to the substantial, recurring nature of its gaming coverage blurring the line between general media and dedicated gaming media.
- `gematsu.com`: Retained `gaming_media` but target market adjusted to `Global` given its audience, though subject matter is Japanese games.

**Questionable Labels Retained**
- `itmedia.co.jp` and `lapresse.ca`: Retained as `uncertain` due to their mixed focus, serving as prime borderline examples for verifier testing.
- `dmm.com`: Retained as `uncertain` as it mixes storefront features with platform features and blocks most foreign IPs, presenting a unique challenge to the verifier.
- `gamewith.jp`: Retained as `uncertain` due to its wiki/guide structure which may or may not satisfy strict editorial requirements depending on the interpretation, and its heavy use of Cloudflare challenges.

**Evidence Limitations**
- Sites requiring Cloudflare traversal (like `gamewith.jp`) or geo-specific IPs (like `dmm.com`) could not be fully verified without advanced infrastructure, hence marked `uncertain`.

**Evidence URL Counts**
- Number of rows with at least one evidence URL: 50
- Number of rows with two evidence URLs: 23

**Uncertain / Inaccessible Counts**
- Number marked `uncertain`: 8
- Number with inaccessible or partially accessible evidence: 4 (`vr-zone.com`, `1up.com`, `dmm.com`, `gamewith.jp`)
