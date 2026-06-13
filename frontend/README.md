# Gaming Media List Toolkit - Frontend

This is the frontend component of the Gaming Media List Toolkit, providing an operator interface for managing and running discovery jobs.

## Requirements
Node.js and npm

## Install
```bash
npm ci
```

## Configuration
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Ensure it contains the API base URL pointing to the backend (by default port 8000):
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Run
Run the development server:
```bash
npm run dev
```

## Build
Build the application for production:
```bash
npm run build
```

## Lint
Run ESLint to check for code quality:
```bash
npm run lint
```
