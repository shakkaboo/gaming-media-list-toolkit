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
