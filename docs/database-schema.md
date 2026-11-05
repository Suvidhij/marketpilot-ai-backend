# Database schema

Implemented in `app/models/entities.py`; versioned by Alembic. User → Client → Lead, Campaign, Content, and Report. All records have primary keys; ownership and parent lookups have indexes; client deletion cascades through foreign keys. SQLite foreign-key enforcement is enabled on every application connection.

| Table | Purpose and key constraints |
| --- | --- |
| users | Normalized unique email, name, Argon2 password hash, active flag, UTC timestamps |
| clients | Owner foreign key, company name, optional HTTP(S) website, industry, description |
| leads | Client foreign key, name/email/source, constrained status, 0–100 score |
| campaigns | Client foreign key, campaign/platform/objective, Decimal budget/spend/revenue, nonnegative performance counters |
| content | Client foreign key, title/platform/type/body, status, optional timezone-aware planned publication time |
| reports | Client foreign key, report name/type, persisted structured JSON snapshot |
| sessions | Hashed random token, owner foreign key, indexed expiry; revocable |
| auth_attempts | Hashed rate-limit subject and timestamp; no raw passwords |
| workflow_tokens | One hashed revocable workflow credential per user |
| workflow_events | Unique user/event ID, payload hash, original result for retries |
| approval_actions | Owner/client, resource reference, immutable payload, review/execution status, external receipt |

Approval action resource references are polymorphic (content or campaign) and checked in the service rather than as a foreign key. Editing/deleting referenced records cancels unclaimed actions; claimed actions block edits/deletion. Deleting the parent client cascades action history after execution has completed.

UTCDateTime restores UTC timezone metadata lost by SQLite. Monetary amounts use Numeric(14,2), not binary floating-point storage. Analytics ratios are rounded to four decimal places and return null on zero denominators. PostgreSQL migration requires a driver, data migration, and deployment checks; portable types and foreign keys are already used, but that migration has not been performed.
