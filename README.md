# MarketPilot AI — Backend

A working marketing workspace API built with Python, FastAPI, Pydantic, SQLAlchemy, SQLite, and Alembic. Includes accounts, session revocation, client-owned records, campaign analytics, reports, six OpenAI agent entry points, and approval-controlled automation.

## A. What are we building?
The private service behind the separate Next.js UI repository. This implementation covers the code for milestones 1–8; live OpenAI, n8n integrations, external publishing, and public deployment require your configured services. See `docs/milestones.md` for precise boundaries.

## B. Why do we need it?
The backend stores business data, checks ownership, calculates metrics, keeps keys out of the browser, and enforces approval before handing consequential actions to an executor.

## C. How the projects communicate
Browser → Next.js `/api/backend/*` proxy → FastAPI `/api/v1/*` → SQLAlchemy → SQLite. The UI and backend repositories should be sibling directories. Full explanation: `docs/architecture.md`.

## D–E. Run locally
Use Python 3.12 and Node.js 24 LTS. From the backend repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

Windows PowerShell: activate with `.venv\Scripts\Activate.ps1`; copy with `Copy-Item .env.example .env`. In a second terminal follow the UI README, then open http://localhost:3000/signup. Create your own account; there are no seeded credentials or fake client records.

API docs: http://localhost:8000/docs. Liveness: `/api/v1/health`. Database readiness: `/api/v1/ready`.

## F. Test
With the virtual environment activated:

```bash
python -m pytest -q
python -m alembic check
```

After building the sibling UI, run the complete HTTP smoke flow against a disposable database:

```bash
python scripts/smoke.py --ui-dir ../marketpilot-ai-ui
```

This exercises the real production UI server, proxy, cookies, signup, owned records, metrics, reports, approval protocol, and logout. It creates synthetic receipts only in its temporary database; it never calls an external publisher. It does not replace browser interaction testing.

## G. Important files

- `app/main.py`: application, CORS, host checks, request limits, safe validation errors, logging.
- `app/core/`: environment settings, database sessions, UTC storage, password/session security.
- `app/models/entities.py`: persisted entities and foreign keys.
- `app/schemas/entities.py`: accepted and returned data shapes.
- `app/api/`: account, record, agent, and workflow endpoints.
- `app/services/`: ownership, campaign calculations, reports, idempotency, approval handoff.
- `app/agents/marketing.py`: six agent instructions, read-only tool calling, structured output.
- `migrations/`: versioned database changes. Application startup does not create tables implicitly.
- `automation/workflows/`: inactive, credential-free n8n exports.
- `tests/`: authorization, sessions, metrics, migrations, AI contract, and automation tests.
- `compose.yaml`: local UI/API deployment with optional n8n.

## H. Troubleshooting

- **No such table / readiness 503:** run `python -m alembic upgrade head` from this repository.
- **401:** sign in; sessions expire and logout revokes them.
- **403:** use the same UI address as `APP_ORIGIN` and `CORS_ORIGINS`. Direct API mutations need `X-MarketPilot-CSRF: 1`; workflow endpoints need `X-Workflow-Key` instead.
- **AI 503:** set `AI_ENABLED=true`, a backend-only `OPENAI_API_KEY`, and an available `OPENAI_MODEL`; restart the API.
- **AI 502:** check provider access, model entitlement, quota, outbound network policy, and backend logs. The response intentionally omits provider secrets.
- **409 workflow:** an event ID has conflicting data, a record has a claimed handoff, or an approval changed. Reuse IDs only for identical retries.
- **429:** wait for the stated retry period; do not disable the check.
- **SQLite locked:** avoid multiple API replicas; keep calls bounded and move to PostgreSQL for scale.

Docker, HTTPS, backups, and rollout instructions: `docs/deployment.md`. n8n setup and action protocol: `automation/README.md`. API overview: `docs/api-documentation.md`.

Recommended managed hosting: [Vercel + Render](docs/vercel-render.md). Verification details and limits: [docs/verification.md](docs/verification.md).
