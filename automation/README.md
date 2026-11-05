# n8n integration

Three inactive, credential-free workflow exports are in `workflows/`: lead qualification, a weekly performance report, and approved-action review. Lead/report endpoints and the approval protocol have automated API coverage. The exports require import and credential assignment in your n8n instance; no live instance has been connected by committing these files.

## Connect

1. Start the app and create a client. Note its ID using the API or client responses.
2. In Automation Centre select **Create workflow key**. Copy the key once. Rotation immediately invalidates the old key; revocation stops all workflow access for that account.
3. Optionally start local n8n from the backend directory: `docker compose --profile automation up -d n8n`. Open http://localhost:5678 and set up its owner account. This local-only admin service uses HTTP; enable TLS and secure cookies before exposing n8n publicly.
4. Import a workflow JSON. Create an n8n **Header Auth** credential with name `X-Workflow-Key` and the copied value; assign it to each HTTP Request node. Never paste the value into an exported JSON file.
5. Update `client_id` and URLs. `http://backend:8000` works within this Compose network. For a separate n8n host use the backend's public HTTPS URL.
6. Run the lead workflow manually. Retry the same execution payload: it must return the original lead ID, not create another lead. Activate the report schedule only after a successful manual test and choosing the intended workflow timezone.

The sample weekly trigger runs Monday at 09:00 in the configured n8n timezone (UTC by default). Set `TZ`/`GENERIC_TIMEZONE` explicitly, for example `Asia/Kolkata`, before activation. Its event ID includes client and ISO week, making scheduler retries safe. The manual lead export uses the n8n execution ID; for a real lead source replace it with the upstream event ID so retried executions cannot duplicate a lead.

## Lead payload

```json
{"event_id":"stable-provider-event-123","client_id":1,"name":"Example lead","email":"lead@example.com","source":"referral"}
```

POST `/api/v1/webhooks/leads`. Scoring is transparent: 20 base + 25 email + 25 inbound/referral/demo (otherwise 5) + 20 qualified, capped at 100. It is a heuristic for prioritization, not a prediction or assessment of a person. The response includes its scoring basis. Invalid payloads return 422 and cross-account client IDs return 404.

POST `/api/v1/webhooks/reports` with `event_id`, `client_id`, and optional `report_name` to save a deterministic performance snapshot without an OpenAI call. Both operations persist a workflow event and support identical retry IDs. Log failed executions in n8n; never regenerate event IDs during retries.

## Consequential actions

1. A user requests publication in Content Studio or a budget change in Campaign Intelligence. The API saves the full proposed payload with status `pending_approval`.
2. A human reviews the exact payload in Automation Centre and approves or rejects it. Edits cancel unclaimed approvals; an approval can be revoked until claimed.
3. A configured executor reads `/api/v1/webhooks/actions` using its credential. Pending/rejected actions are not returned.
4. POST `/api/v1/webhooks/actions/{id}/claim`. The backend atomically claims an approved action, returns the immutable payload, and supplies `marketpilot-action-{id}` as the external provider idempotency key. Repeated claims return the same handoff; they are recovery requests, not permission to duplicate an external action.
5. The executor calls your specifically configured publishing or advertising integration using that idempotency key. The provided review workflow does not contain such a provider call.
6. Only after confirmed success POST `/api/v1/webhooks/actions/{id}/complete` with `{ "external_reference": "provider-receipt-id" }`. The API then marks content published or updates the local budget. Identical completion retries are safe; conflicting receipts return 409.

Never call complete for a failed or uncertain provider response. An uncertain executing action remains locked for investigation; use the provider idempotency key to recover/confirm it before completion. A provider without idempotency support needs additional reconciliation and cannot guarantee exactly-once execution. The workflow credential is trusted to report truthful external receipts; keep it secret.

Live competitor monitoring, platform metrics ingestion, notifications, and additional provider-specific workflows require the corresponding data sources, credentials, and destination choices. The research agent does not pretend to have crawled competitor websites.
