# MarketPilot AI — Backend

Phase 1 FastAPI + Python + Pydantic foundation. This service currently exposes only health and generated API documentation. Database, accounts, business data, OpenAI, and n8n integrations are deliberately deferred to the milestones in the supplied brief.

## A. What are we building?
An independent API service that the Next.js UI can call.

## B. Why do we need it?
The backend will eventually validate requests, enforce record ownership, and keep database and OpenAI credentials away from the browser.

## C. How it works
FastAPI routes a health request to `app/api/health.py`. Pydantic defines its response. Configuration reads environment variables using `pydantic-settings`. CORS allows only explicitly configured frontend origins. CORS is a browser control, not authentication; this health endpoint is intentionally public.

## D–E. Run it
Prerequisites: Python 3.12 and Git. Open a terminal in this repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

Windows PowerShell: activate with `.venv\Scripts\Activate.ps1` and copy with `Copy-Item .env.example .env`.

Open http://localhost:8000/docs for interactive API documentation. The UI runs separately at http://localhost:3000.

## F. Verify
In another terminal with the virtual environment activated:

```bash
python -m pytest -q
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{"status":"ok","service":"MarketPilot AI API","version":"0.1.0"}
```

Tests check the response contract, trusted and untrusted origins, rejected preflight methods, and missing routes. This health check proves the process responds; it does not claim database readiness.

## G. Important files

- `app/main.py`: application factory, API router, CORS configuration.
- `app/core/config.py`: typed environment configuration.
- `app/api/health.py`: health route and response schema.
- `tests/test_health.py`: health and CORS tests.
- `.env.example`: safe local configuration template.
- `requirements.txt`: runtime dependency versions.
- `requirements-dev.txt`: additional test dependencies.

Future modules will live under `models`, `schemas`, `services`, `agents`, and `integrations` as working features are implemented. We do not create nonfunctional agents or unprotected business endpoints in Phase 1.

## H. Troubleshooting

- **Module not found:** activate `.venv`, install requirements, and run commands from this repository root.
- **CORS error:** set `CORS_ORIGINS` as a JSON array, for example `["http://localhost:3000"]`. Restart the backend after configuration changes.
- **Port in use:** stop the other service or choose another port; update the UI API address to match.
- **Configuration validation error:** use the formatting shown in `.env.example`.

The local server is a development service. Before production, complete database migrations, secure authentication and authorization, HTTPS, deployment configuration, rate limits, and operational monitoring. No OpenAI key is required yet.
