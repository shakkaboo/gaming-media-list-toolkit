# Gaming Media Discovery API (Backend)

This is the new backend foundation for the Automated Gaming Media Discovery and Qualification Platform. 

## Phase 1 Scope
Currently, this backend only implements the **Phase 1 MVP Foundation**:
- Application configuration and environment parsing
- Database connection foundation (SQLAlchemy)
- Logging configuration
- Health endpoints (`/api/health`)

**Notice:** PostgreSQL models, actual search providers, and automated discovery logic are **not** implemented yet. The existing CSV-driven application (`media-list-generator` and `media-list-dashboard`) remains entirely untouched and fully operational during this phase.

## Prerequisites
- Python 3.10+
- PostgreSQL (for future phases)

## Setup Instructions (Windows)

1. **Create and activate a virtual environment:**
```powershell
python -m venv .venv
# PowerShell:
.venv\Scripts\Activate.ps1
# Or Command Prompt:
.venv\Scripts\activate.bat
```

2. **Install dependencies:**
```powershell
pip install -r requirements.txt
```

3. **Configure the environment:**
```powershell
Copy-Item .env.example .env
```
*(Open `.env` and adjust the PostgreSQL connection string as needed).*

## Running the Server

Start the FastAPI application with Uvicorn:
```powershell
uvicorn app.main:app --reload
```

## Running Tests

Execute the test suite using pytest:
```powershell
pytest
```

## Available URLs
Once running, the following endpoints are available:
- **Root**: `http://localhost:8000/`
- **Health Check**: `http://localhost:8000/api/health`
- **Config Check**: `http://localhost:8000/api/health/config`
- **Swagger Documentation**: `http://localhost:8000/docs`
