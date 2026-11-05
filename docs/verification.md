# Verification record

- Backend: 28 tests passed, including registration/login, Argon2 hashing, session expiration/revocation, password changes, CSRF, ownership isolation, CRUD/cascades, metric calculations, input limits, workflow authentication/replay, approval requirements, immutable claimed actions, SDK tool-call contract, migration upgrade/downgrade/metadata consistency, readiness, and private consistent backups.
- Dependency consistency: `pip check` passed; `alembic check` reported no new upgrade operations.
- Frontend: four HTTP error/session-response tests passed; TypeScript check passed; Next.js production build passed.
- Production HTTP smoke: real Next.js standalone server and FastAPI with a temporary SQLite database passed public/protected page responses, proxy cookie forwarding, signup, cross-account isolation, CRUD, metrics, reports, approval/claim/completion protocol, and logout. This uses synthetic receipts and makes no real external publication or advertising changes.
- UI container: standalone server startup, landing page, static CSS delivery, login, and protected-route redirect passed.
- Backend container: migration startup, database readiness, account registration, and cookie-authenticated user lookup passed after correcting non-root source-file ownership. To fit the available disk, final runtime verification reused the built dependency image with the corrected application files. A clean build of the original image had already succeeded; the final full Dockerfile was not rebuilt from scratch after that ownership correction.
- Deployment files: Compose production configuration was parsed with placeholder domains; Render YAML and Vercel JSON were parsed locally. This does not verify a provider deployment.
- UI runtime dependency audit: npm reported zero known vulnerabilities at the time of this check. This is a package advisory check, not a security audit of the application or a guarantee about future advisories.

Not exercised: a live OpenAI account, live n8n execution/scheduling, real external publishing/advertising integrations, public hosting/DNS/TLS provisioning, or actual browser interactions/visual rendering. One upstream test-client deprecation warning remains; it did not fail the tests.

The task's local disk reached its limit during container builds. Only task-generated local caches/dependencies were removed. Automatic approval review rejected broader shared Docker-cache pruning, so that cleanup was not performed and the optional n8n image was not pulled. No existing project data, repository source, or shared Docker volumes were removed.
