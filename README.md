# Anvikshiki

**Status: Building phase**

Anvikshiki is a local AI-powered conversation system built with FastAPI for the backend and Vite + React for the frontend. It is currently under active development, so the implementation is not complete and the API/UX may still change.

## Project Overview

- `app/` — backend service implementation
- `frontend/` — React frontend
- `data/` — local runtime artifacts and stores (not tracked in git)
- `tests/` — automated test suite
- `.env.example` — sample environment variables for local development
- `requirements.txt` — Python backend dependencies

## What belongs in this repository

Keep these in git:

- source code under `app/` and `frontend/`
- `requirements.txt`
- `package.json`
- `README.md`
- `tests/`
- `.env.example`
- `.gitignore`
- `real_sample.txt` (if it is intentionally part of the project)

## What should not be committed

Do not commit generated or machine-specific files:

- `.venv/`
- `data/`
- `.env`
- `__pycache__/`
- `*.pyc`

The existing `.gitignore` already excludes the key runtime artifacts.

## Local setup

1. Create a Python virtual environment:

   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

3. Copy `.env.example` to `.env` and update values as needed.

## Running locally

Backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

## Testing

Run the Python tests with:

```bash
pytest -q
```

## Notes

- The backend is built with FastAPI and includes request tracing, event logging, and a modular dialogue pipeline.
- The frontend is a Vite + React app and is currently configured for local development.
- The project is a work in progress, so breaking changes may still occur.
