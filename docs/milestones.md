# Milestones and delivery boundaries

This delivery implements the application code across the eight requested milestones in one pass. External provisioning and verification are listed separately so an unconfigured integration is never presented as working.

| Milestone | Implemented |
| --- | --- |
| 1. Setup | Two Git repositories, Next.js/TypeScript/Tailwind, modular FastAPI, configuration templates, CI and documentation |
| 2. Database | SQLAlchemy entities, SQLite foreign keys and indexes, ownership services, Alembic migration and round-trip tests |
| 3. Authentication | Registration, Argon2 hashing, HttpOnly sessions, expiration, logout revocation, password changes, CSRF/origin checks, protected routes and ownership tests |
| 4. Dashboard | Responsive navigation, overview, client CRUD, profile settings, real API integration, empty/loading/error states |
| 5. First AI integration | Backend OpenAI SDK, constrained read-only tool, structured Pydantic outputs, saved research reports, clear unconfigured/provider errors |
| 6. Automation | Authenticated lead/report webhooks, persisted idempotency receipts, activity log, credential rotation, approval/claim/completion protocol, three inactive n8n exports |
| 7. Expansion | Six agent entry points; lead, campaign and content CRUD; CTR/CPC/CPM/CPL/ROAS; saved performance history; reports and downloads; strategist UI |
| 8. Testing/deployment | Backend and frontend tests, real production HTTP smoke flow, Docker images, local Compose, HTTPS production overlay, backup utility, rollout guide |

## Still dependent on external setup

- OpenAI: no live key is configured; provider behavior is tested with a simulated SDK contract and graceful unconfigured responses. Billing, model entitlement, and outbound API access must be verified in the deployment.
- n8n: exports are ready to import and configure. Live n8n scheduling and execution have not been run. The optional image was not pulled because the task environment reached its disk limit.
- External publishing/advertising: an approved handoff is implemented; a provider-specific executor and truthful external receipt are still required. Tests use synthetic receipts in disposable databases and perform no real publication or budget change.
- Website/competitor intelligence: agents use saved business context and report history. No live crawler, search/keyword provider, advertising sync, or RAG knowledge source is connected.
- Hosting: the production stack is prepared for a Docker server and HTTPS domains, but Vercel/Render setup is recommended and documented, but no connected hosting account or DNS access has been supplied and no public deployment has occurred.
- Browser QA: automated tests cover API behavior, request handling and HTTP-rendered pages. Actual browser form interaction, keyboard flow, and visual rendering remain to be checked.
- Commercial hardening: verified email and forgotten-password recovery, monitoring/alerts, operational rate controls, recovery drills, privacy/data-retention policy, and scale-out infrastructure require further work.

The delivered implementation is a functional MVP. These boundaries prevent interpreting repository code, importable workflows, or deployment instructions as evidence that a live external service has been provisioned.
