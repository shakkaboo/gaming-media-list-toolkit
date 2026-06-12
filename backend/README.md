# Gaming Media Discovery API (Backend)

This is the backend foundation for the Automated Gaming Media Discovery and Qualification Platform.

## Phase 1 Scope
- Application configuration and environment parsing
- Database connection foundation (SQLAlchemy)
- Logging configuration
- Health endpoints (`/api/health`)

## Phase 2A Scope
- Modular SQLAlchemy 2.x declarative models.
- PostgreSQL constraints, enums, indexes, and portable UUID handling.
- Alembic migration setup.

## Phase 2B Scope
- Application Exceptions mapped to standard HTTP status codes (400, 404, 409).
- Pydantic v2 schemas validating payload boundaries and formatting relationships.
- Service layer handling business logic and strict PostgreSQL transactions.
- REST API Routers exposing data access without actual scraping logic.
- **Important:** Internet discovery, query generation, automated traffic fetching, and Brave search logic remain **unimplemented**.

### Endpoints
#### Discovery Jobs
- `POST /api/discovery/jobs`: Generates a pending job
- `GET /api/discovery/jobs`: Lists paginated jobs
- `GET /api/discovery/jobs/{job_id}`: Job detail

#### Websites
- `GET /api/websites`: Lists paginated websites with search and extensive filters
- `GET /api/websites/{website_id}`: Full website detail including traffic history, contact logs, and errors
- `PATCH /api/websites/{website_id}/review`: Change manual review status safely
- `POST /api/websites/{website_id}/traffic`: Submit manual metrics

### Features & Behaviors
- **Pagination**: Consistent generic `PaginationMeta` returned across listing endpoints.
- **Filters**: Extensive text searching and categorical listing available on Websites.
- **Example Job Creation Request**:
  ```json
  {
    "target_market": "US",
    "language": "en",
    "categories": ["RPG", "Action"],
    "minimum_pageviews": 1000000,
    "maximum_queries": 10,
    "results_per_query": 10
  }
  ```
- **Decimal Pageview Calculation**: Traffic values are multiplied accurately as fixed-point Decimals ensuring precise rounding.
- **Qualification Strict `>` Rule**: Estimated pageviews precisely matching the threshold map to `upcoming`, whilst those strictly greater map to `qualified`.
- **Computed Effective Review Decision**: A calculated string merges manual overrides and automated validation outputs natively inside the WebsiteSummary payload without inflating the database layer.
- **Real PostgreSQL requirement**: To accurately evaluate transaction commits, JSON storage, and relationship ordering, a real PostgreSQL environment is mandatory. SQLite is not an accurate emulator. 
- **Offline Unit-Test Limitations**: Tests mock service boundaries ensuring endpoint logic works cleanly offline but they do not execute physical SQL queries on real database records.

## Phase 3A Scope
- Search Query Generation combining languages, markets, categories, and keyword overrides safely.
- Abstract search provider interface supporting deterministic offline Mock implementations and live Brave Search wrappers via `httpx`.
- Environment-configured safety rails: `MAX_SEARCH_CONCURRENCY`, `SEARCH_REQUEST_TIMEOUT_SECONDS`, and `SEARCH_RESULTS_PER_QUERY`.
- Explicit API Previews mapping error statuses cleanly (e.g. Rate Limits -> 429, Config Issues -> 400).
- **Explicit Limitation**: Returned sites are merely JSON schemas representing URLs. They are **not** normalized, deduplicated, fetched, classified, or stored inside the PostgreSQL database yet. Automatic discovery jobs are not yet working.

### Preview Endpoints
#### POST `/api/search/queries/preview`
Returns generated search queries natively without launching HTTP search fetches.

Example payload:
```json
{
  "market": "UK",
  "language": "en",
  "categories": ["esports"],
  "keywords": ["dota 2 tournament"],
  "maximum_queries": 5
}
```

#### POST `/api/search/results/preview`
Generates queries and actively retrieves bounded result structures through the selected provider (`mock` or `brave`).

### Testing & Validation
- Testing executes Mock and Brave Search validations securely via `respx` mocked boundaries avoiding arbitrary network overhead and eliminating the need for paid API credits.
- Errors emitted dynamically return safe JSON dictionaries reflecting the failure context without dumping credentials or stack-traces.
- Rate-limiting (HTTP 429) actively extracts `Retry-After` metrics, gracefully awaiting cooldowns natively inside Python via `asyncio.sleep`, shielding upstream engines.

## Phase 3B Scope
- **URL Normalization**: Normalizes schemes and hosts, removes fragments and known tracking parameters (`utm_*`, `gclid`, etc.), while securely extracting registered domains and subdomains using `tldextract`.
  - Example: `https://WWW.ExampleGaming.COM/news?id=5#top` -> `https://examplegaming.com/news?id=5`
- **Domain Filtering**: Configurable static blocklists reject infrastructure hosts, social media, streaming platforms, forums, marketplaces, URL shorteners, and search engines.
- **Multi-tenant Handling**: Multi-tenant platforms (like `substack.com`, `wordpress.com`, `blogspot.com`) use full subdomains for deduplication, while standard sites deduplicate on the registered domain.
  - *Limitation*: `medium.com` is strictly blocked by default in Phase 3B because its internal publisher identity requires path-based differentiation, which is beyond current domain-level normalization.
- **Candidate Deduplication**: Winners are chosen by earliest generated query, lowest result position, and HTTPS preference. Duplicates are tracked via counters and optional provenance lists rather than rejected.
- **Explicit Limitation**: Returned candidates are completely ephemeral API previews. They are **not** fetched for HTML scraping, DNS-resolved, classified via AI, checked for traffic, nor persisted into PostgreSQL storage yet.

### Preview Endpoints
#### POST `/api/search/candidates/preview`
Generates search queries, fetches raw URLs (Mock or Brave), normalizes the results, applies blocklist filtering, and executes deduplication.

Example payload:
```json
{
  "market": "UK",
  "language": "en",
  "categories": ["esports"],
  "keywords": ["dota 2 tournament"],
  "maximum_queries": 5,
  "results_per_query": 10,
  "provider": "mock",
  "include_rejected": true,
  "include_duplicates": false
}
```

## Phase 3C Scope
- **Safe Asynchronous Fetching**: Safely fetches bounded homepage HTML content for normalized candidates.
- **Separate Fetch-Preview Endpoint**: Exposed via `POST /api/fetch/preview` accepting normalized candidates directly, decoupled from search execution.
- **Internal vs Public Scope**: Retains full, bounded HTML internally up to `MAX_HTML_RESPONSE_BYTES` (2MB). Exposes only truncated `html_preview` to public clients.
- **SSRF Protections & DNS Validation**: Pre-validates hostnames to prevent metadata scraping. Re-resolves hostnames safely with `socket.getaddrinfo`, blocking loopback, private ranges, link-local IPs, etc., before establishing connections.
- **Redirect Validation**: Follows up to 5 redirects manually to prevent redirect-based SSRF. Blocks HTTPS downgrades.
- **Streaming & Content Limits**: Streams responses via `httpx` checking declared and decompressed size. Blocks fetching anything other than `text/html` and `application/xhtml+xml`.
- **TLS Enforcement**: Mandates strict TLS validation (`verify=True`).
- **Retry Behavior**: Bounded exponential backoff with capped delays, explicitly handling 500, 502, 503, 504 and transient timeouts. Does NOT retry on 4xx, oversized payloads, or decoding errors.
- **Robots Policy Deferral**: Defers `robots.txt` enforcement to a later contact crawling phase (Phase 4), treating this bounded homepage lookup similar to a user navigation.
- **Explicit Security Limitations**: Contains a known Time-of-Check to Time-of-Use (TOCTOU) DNS-rebinding gap since `httpx` internally re-resolves the IP after initial validation. Perfect protection requires customized low-level transport.
- **Explicit Feature Limitations**: Performs **no** gaming media classification, contact extraction, traffic metric lookups, recursive crawling, or PostgreSQL database writes.

## Setup Instructions (Windows)

1. **Create and activate a virtual environment:**
```powershell
python -m venv .venv
# PowerShell:
.\.venv\Scripts\Activate.ps1
# Or Command Prompt:
.\.venv\Scripts\activate.bat
```

2. **Install dependencies:**
```powershell
pip install -r requirements.txt
```

3. **Configure the environment:**
```powershell
Copy-Item .env.example .env
```

### PostgreSQL Database Configuration

For Phase 2A, you need a local PostgreSQL instance to run the integration migrations.
1. Install PostgreSQL and pgAdmin (or use a docker container).
2. Create a new database manually via pgAdmin or psql:
```sql
CREATE DATABASE gaming_media;
```
3. Open your `.env` file and set the `DATABASE_URL` using the psycopg3 dialect format:
```text
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/gaming_media
```

## Alembic Migration Workflow

Alembic manages all database schemas.

To run migrations and create the tables in your PostgreSQL database:
```powershell
alembic upgrade head
```

To see the current migration state:
```powershell
alembic current
```

To undo the last migration:
```powershell
alembic downgrade -1
```

To view the migration history:
```powershell
alembic history
```

## Running Tests

Execute the test suite using pytest. The tests are designed to run metadata inspections offline without requiring a live PostgreSQL server.
```powershell
pytest
```

## Available URLs
Once running via `uvicorn app.main:app --reload`:
- **Root**: `http://localhost:8000/`
- **Health Check**: `http://localhost:8000/api/health`
- **Config Check**: `http://localhost:8000/api/health/config`
- **Swagger Documentation**: `http://localhost:8000/docs`
