# API reference

Base path `/api/v1`. Full interactive specification: `/docs`; machine-readable schema: `/openapi.json`.

| Area | Endpoints |
| --- | --- |
| Health | GET `/health`, GET `/ready` |
| Account | POST `/auth/register`, `/auth/login`, `/auth/logout`; GET/PATCH `/auth/me`; POST `/auth/password` |
| Clients | GET/POST `/clients`; GET/PUT/DELETE `/clients/{id}`; GET `/clients/{id}/overview` |
| Leads, campaigns, content | GET/POST `/clients/{id}/{resource}`; GET/PUT/DELETE `/clients/{id}/{resource}/{record_id}` |
| Reports | GET/POST `/clients/{id}/reports`; GET/DELETE `/clients/{id}/reports/{report_id}` |
| AI agents | POST `/clients/{id}/agents/run`, body `{ "agent": "research", "question": "..." }` |
| Workflow credential | GET `/automation/status`; POST/DELETE `/automation/token` |
| Approval requests | GET/POST `/automation/actions`; POST `/automation/actions/{id}/decision` |
| Activity | GET `/automation/events` |
| Incoming workflows | POST `/webhooks/leads`, POST `/webhooks/reports` |
| External executor | GET `/webhooks/actions`; POST `/webhooks/actions/{id}/claim`; POST `/webhooks/actions/{id}/complete` |

Cookie authentication uses `marketpilot_session`. All non-workflow mutations require `X-MarketPilot-CSRF: 1`; a browser Origin, when present, must be explicitly trusted. Next.js sets this header after validating the UI origin. Workflow routes accept only `X-Workflow-Key` credentials and do not use session cookies. Responses never include password or credential hashes.

List clients and nested resources with `offset` (default 0) and `limit` (default 100, maximum 1,000). The UI paginates resources in batches of 25 and loads up to the latest 1,000 clients. PUT replaces the full editable record. Content status is controlled by approval/execution endpoints, not by its edit form.

Agent values: `research`, `content`, `campaign`, `lead`, `reporting`, `strategist`. Success stores a Report containing the parsed result, model, source context, limitations, and provider response ID. Missing configuration returns 503; provider failure returns 502. No mock fallback is used by the running application.

Workflow payloads must contain a stable `event_id` and owned `client_id`. Identical retries return `duplicate: true`; conflicting reuse returns 409. See `automation/README.md` for payload examples and the approval protocol.

Errors: 401 authentication; 403 origin/CSRF; 404 missing or inaccessible record; 409 conflict/claimed action; 413 body over 1 MB; 422 validation; 429 throttling; 502 provider/backend failure; 503 readiness/configuration. Validation responses omit submitted inputs. Logs include `X-Request-ID` for correlation.
