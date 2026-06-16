# Current Verifier Inventory

**Exact Files**
- `backend/app/services/verification_service.py`
- `backend/app/verification/classifier.py`
- `backend/app/verification/rules.py`
- `backend/app/verification/html_analyzer.py`

**Exact Classes**
- `VerificationService`
- `Classifier`
- `HtmlAnalyzer`

**Exact Functions**
- `VerificationService.verify_candidates`
- `VerificationService._verify_page_sync`
- `VerificationService._create_error_result`
- `Classifier.classify`
- `evaluate_gaming_relevance`
- `evaluate_editorial_structure`
- `evaluate_activity`
- `evaluate_publication_identity`
- `evaluate_negative_penalties`
- `detect_categories`
- `HtmlAnalyzer.analyze`
- `HtmlAnalyzer._extract_metadata`
- `HtmlAnalyzer._extract_headings`
- `HtmlAnalyzer._extract_navigation_and_footer`
- `HtmlAnalyzer._extract_links`
- `HtmlAnalyzer._extract_time_elements`
- `HtmlAnalyzer._extract_json_ld`
- `HtmlAnalyzer._traverse_json_ld`
- `HtmlAnalyzer._detect_challenges`

**Current Inputs**
- `FetchedPage` (containing HTML content, URLs, response headers)
- `VerificationRequest` (containing thresholds and candidates)

**Current Outputs**
- `VerificationResult` containing fields like `verification_status` (`verified`, `uncertain`, `rejected`, `fetch_failed`), `score`, `confidence`, `positive_reasons`, `negative_reasons`, `detected_categories`, and `activity_status`.

**Current Positive Signals**
- Gaming terminology in metadata (Title, Description, Open Graph tags)
- Platform terminology in navigation labels or headings
- Gaming context or structured data (`VideoGame`, `esports`)
- Editorial navigation labels (`news`, `reviews`, `guides`, etc.)
- Article-like links
- Editorial JSON-LD schema (`NewsArticle`, `Review`, etc.)
- Recent publication dates (within 90 days = active, within 365 days = possibly active)
- Open Graph site name
- Author/byline links
- About/Team links (editorial footprint)
- Explicit publication wording

**Current Negative Signals**
- E-commerce or store signals (`shopping cart`, `buy now`)
- Developer or publisher signals (`our games`, `developed by`)
- Casino or betting signals (`casino`, `gambling`, `betting`)
- Hardware retailer signals (`graphics card`, `gpu`)
- Cloudflare challenge or access denied pages
- Parked domains or domains for sale

**Current Thresholds**
- `score` must be `>= GAMING_MEDIA_VERIFIED_THRESHOLD` (with `gaming_score >= 18` and `editorial_score >= 18`) to be `verified`.
- `score` must be `>= GAMING_MEDIA_UNCERTAIN_THRESHOLD` to be `uncertain` (or high score but missing minimum subscores).
- Otherwise, the site is `rejected`.
- Confidence is adjusted based on specific penalties or missing editorial structures.

**Current Fetch-Failure Behavior**
- Automatically returns `fetch_failed` status with a score of 0, confidence of 0.0, and a negative reason specifying `fetch_failed`.

**Traffic Affects Relevance Classification?**
- Not confirmed from current implementation. (Traffic data is not evaluated by the verification logic).

**Any Score Currently Calculated?**
- Yes, a `raw_score` is computed by adding gaming, editorial, activity, and identity scores and subtracting negative penalties, which is then bounded between 0 and 100.

**Any Labelled Game-Domain Dataset Currently Used?**
- Not confirmed from current implementation. The current logic uses rule-based matching (`CLASSIFIER_VERSION = "rule_based_v1"`) with hardcoded regex patterns.
