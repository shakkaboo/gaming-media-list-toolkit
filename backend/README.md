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
- Alembic migration environment setup and initial core schema script.
- **Notice:** CRUD endpoints are **not yet implemented**. Discovery logic, actual search providers, and scraping are **absent**.
- **Important:** Do NOT use `Base.metadata.create_all()`. Use Alembic exclusively for schema management.

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
