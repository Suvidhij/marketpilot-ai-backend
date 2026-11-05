# Run and deploy MarketPilot AI

For the recommended managed option, start with [Vercel + Render](vercel-render.md). The Docker paths below are an alternative.

## Local containers

Install Docker with Compose. Clone both repositories side by side, preserving their directory names:

```bash
mkdir marketpilot-ai
cd marketpilot-ai
git clone https://github.com/Suvidhij/marketpilot-ai-ui.git
git clone https://github.com/Suvidhij/marketpilot-ai-backend.git
cd marketpilot-ai-backend
cp .env.example .env
docker compose up --build -d
```

Open http://localhost:3000/signup. The backend is available at http://localhost:8000/docs. SQLite lives in the named `marketpilot-data` volume and survives container replacement. API startup applies Alembic migrations before serving. Both images run as non-root users.

```bash
docker compose ps
docker compose logs --tail=100 backend ui
docker compose down
```

`down` preserves data volumes. Do not add `--volumes` unless you intentionally want to delete local database and n8n data.

Optional local n8n: `docker compose --profile automation up -d n8n`. Open http://localhost:5678, create its owner account, and follow `automation/README.md`. n8n uses a separate persistent volume. Its local HTTP cookie setting is unsuitable for a public admin endpoint.

## OpenAI

Set `AI_ENABLED=true`, `OPENAI_API_KEY`, and an available `OPENAI_MODEL` in the backend's untracked `.env`. The model defaults to `gpt-4.1-mini`; availability depends on your account. Recreate the backend: `docker compose up -d --force-recreate backend`. Allow outbound HTTPS to `api.openai.com` in your hosting environment. The current task environment has no OpenAI key and does not allow that API destination, so no live provider request has been verified here. Do not paste keys into chat or commit them.

## Public HTTPS deployment on a Docker server

The included production overlay targets a single Linux server with Docker. It preserves Python/FastAPI and Next.js without substituting a different backend runtime. You need a server account, two domain names with DNS pointing at the server, and inbound ports 80/443. These infrastructure resources have not been provisioned.

Clone the sibling repositories on the server and copy `.env.example` to `.env`. Add your actual domains:

```dotenv
APP_DOMAIN=app.your-domain.example
API_DOMAIN=api.your-domain.example
APP_ORIGIN=https://app.your-domain.example
```

Replace these example names before starting. Protect `.env` with owner-only filesystem permissions. Add your OpenAI values only if AI should be enabled. The overlay sets production mode, Secure cookies, HTTPS CORS origins, and trusted hosts from those domains.

```bash
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up --build -d
```

Caddy obtains and renews TLS certificates when DNS and ACME access are working. UI and API ports stay bound to server loopback; Caddy is the public ingress. Set the n8n HTTP request URLs to the public API HTTPS domain for an externally hosted instance. Keep n8n administration local or put it behind a separately configured authenticated HTTPS endpoint; do not expose the development port directly.

Before directing customers to a deployment, perform signup/login/logout checks over HTTPS, verify secure cookies and ownership, test backup restoration, configure operational alerts and external rate controls, and connect provider-specific workflows in a test account. Email verification and forgotten-password recovery need an email service and are not implemented. This is a functional MVP, not a claim of an audited commercial production service.

## Database changes and backups

Create future migrations with `python -m alembic revision --autogenerate -m "describe change"`, review the generated operations, then apply with `python -m alembic upgrade head`. Never replace a populated database with `create_all`. A database downgrade can destroy data; back up before changing schemas and prefer compatible forward fixes.

From a running backend container, create a consistent SQLite backup using the SQLite backup API:

```bash
docker compose exec backend python -m app.utils.backup /app/data/backups/before-release.sqlite3
```

The destination must not already exist. The utility checks SQLite integrity and creates a file readable only by its owner. Copy backups to access-controlled off-server storage; a backup on the same server is insufficient for disaster recovery. Test restoration against a disposable database first. For live restoration, stop writers, preserve the current database separately, replace the database from the verified backup with the correct volume ownership, then restart and verify readiness and account records.

SQLite is appropriate for this single-instance MVP. Add PostgreSQL, a proper job queue, central rate limiting, and shared operational monitoring before scaling to multiple API replicas.

## Build environments with an HTTPS proxy

Dockerfiles accept an optional BuildKit secret called `proxy_ca` for dependency installation. In a managed cloud environment use the configured system CA bundle, keep existing proxy settings, and keep TLS verification enabled:

```bash
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t marketpilot-backend:local .
```

Build the UI similarly from its repository. The CA is mounted only during installation and is not copied into runtime image layers. For runtime external calls behind a private CA proxy, mount your combined CA bundle read-only and set the client's trust variable; do not disable certificate validation.
