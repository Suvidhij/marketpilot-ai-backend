# Recommended managed hosting: Vercel + Render

For a beginner, these services avoid maintaining a server and TLS certificates. Vercel hosts the Next.js UI. A paid, single-instance Render Python service with a persistent disk hosts FastAPI and SQLite. Free/ephemeral filesystem services are unsuitable for this SQLite database. Check current service pricing before accepting a plan; no paid resources have been provisioned by this code change.

The backend repository includes `render.yaml`; the UI includes `vercel.json`. A custom domain is optional initially: both services provide HTTPS domains. These configuration files have been prepared locally; no account connection or live deployment has happened.

## 1. Create the Vercel UI project

In Vercel, import `Suvidhij/marketpilot-ai-ui`. Use the Next.js preset and deploy. The public landing/signup pages can build before a backend exists, but signup will not function until step 3. Record your stable production URL, such as `https://your-project.vercel.app`. Keep preview deployments disconnected from production client data unless you configure their exact origins deliberately.

## 2. Create the Render backend

In Render, connect `Suvidhij/marketpilot-ai-backend` and create a Blueprint from `render.yaml`. Review the paid service and disk settings before creating resources. The service uses native Python, the same application code and stack as Docker, and applies Alembic before it starts.

Set the prompted variables:

- `CORS_ORIGINS`: a JSON array containing the exact production Vercel URL, for example `["https://your-project.vercel.app"]`.
- `ALLOWED_HOSTS`: a JSON array containing the exact hostname assigned to this Render service plus `localhost` and `127.0.0.1`, for example `["your-backend.onrender.com","localhost","127.0.0.1"]`.

Copy the actual assigned names from your dashboards, not these examples. The Blueprint requires Secure cookies and HTTPS frontend origins. The database file is `/var/data/marketpilot.db` on the persistent disk. Do not enable multiple replicas or replace the database path with the ephemeral application directory.

Check that `https://YOUR_BACKEND/api/v1/ready` returns `{"status":"ready"}`. If it fails, inspect Render logs, environment-variable JSON formatting, migration output, and the selected disk mount. An unsupported exact Python patch version can be changed to the latest Render-supported Python 3.12 patch after checking their version list.

## 3. Connect the UI

In Vercel production environment variables, set:

```dotenv
API_BACKEND_URL=https://YOUR_ACTUAL_RENDER_HOST
APP_ORIGIN=https://YOUR_ACTUAL_VERCEL_HOST
```

Redeploy the UI. These are server configuration values; no `NEXT_PUBLIC_` variables are needed. Verify `/status`, create an account, add a client and campaign, save a report, then sign out and check that `/dashboard` redirects to login. Confirm the session cookie has HttpOnly, Secure, and SameSite=Lax attributes. A custom UI domain requires changing both `APP_ORIGIN` and backend `CORS_ORIGINS`.

The API proxy is configured for a 90-second function limit. Confirm your Vercel plan permits this; AI consists of two bounded provider calls. A lower platform timeout can interrupt a request, in which case move AI work to a background-job service before relying on long responses.

## 4. Enable AI and automation deliberately

Set `OPENAI_API_KEY` as a secret on Render and `AI_ENABLED=true`; use an available `OPENAI_MODEL`. Redeploy/restart and run a research request using actual saved client context. Never put the key in Vercel's public variables or in a repository.

For the least server maintenance, use n8n Cloud. Import the backend workflow exports, create the Header Auth credential described in `automation/README.md`, change their base URL to the Render HTTPS host, and replace sample client IDs. Test manually before enabling the Monday report schedule. Provider-specific publishing and advertising executors still require their own accounts, credentials, and idempotency/reconciliation behavior.

## 5. Operate it

Back up the SQLite database to access-controlled off-service storage and practice restoration. Deploy compatible schema changes, keep the disk mounted, monitor readiness/error rates, and complete email recovery/verification before a public commercial launch. See `deployment.md` for the backup command and broader operating boundaries.
