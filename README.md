# Gaming Media List Toolkit

A dual-module automation toolkit for gathering, qualifying, and presenting high-traffic gaming media publications.

## Modules

The project is split into two distinct modules:

### 1. Backend (FastAPI / PostgreSQL)
Located in `/backend`, this Python service orchestrates the discovery, verification, and qualification workflows.

**How to run:**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Configure DATABASE_URL in .env
alembic upgrade head
python -m uvicorn app.main:app --reload
```

### 2. Frontend (React / Vite)
Located in `/frontend`, this React Vite application provides the operator dashboard.

**How to run:**
```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

For more details, see the specific READMEs inside the `backend` and `frontend` directories.
