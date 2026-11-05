# Architecture and milestone boundaries

The original brief describes one parent directory. This delivery uses two independent repositories because the owner requested separate UI and backend repositories. The UI repository root corresponds to `frontend/`; the backend repository root corresponds to `backend/`. Documentation is kept beside the code it describes. Future n8n workflow exports will live under the backend repository's `automation/workflows/` directory, separate from API logic.

```text
Browser → Next.js UI (localhost:3000)
               ↓ HTTP GET /api/v1/health
          FastAPI (localhost:8000)
               ↓ planned in Phase 2
          SQLAlchemy → SQLite
```

Phase 1 contains a landing page, connection-check UI, versioned health API, typed configuration, automated API tests, dependency manifests, CI, and documentation. There is no user database, login, client CRUD, agent, or external API connection yet.

Next: Phase 2 adds SQLAlchemy models and Alembic migrations, followed by Phase 3 authentication and ownership enforcement. Phase 4 adds the protected dashboard and client interface. Phase 5 adds server-side OpenAI services. Phase 6 adds authenticated, validated, idempotent n8n webhooks. Consequential publishing and budget actions will require human approval.

Configuration and secrets are excluded from Git. The frontend only receives a public backend URL. Passwords and API keys must never enter frontend source, browser storage, or public environment variables. Database ownership must be checked on the backend for every future business endpoint.

Health checks currently measure liveness only. Readiness checks will be introduced alongside the dependencies they actually verify.
