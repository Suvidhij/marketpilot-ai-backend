# Proposed database schema — Phase 2

This is a design document, not an implemented database. SQLAlchemy models and Alembic migrations will be introduced and tested in the next milestone.

| Entity | Fields |
| --- | --- |
| User | id, name, email (unique, normalized), hashed_password, is_active, created_at, updated_at |
| Client | id, user_id (FK User, indexed), company_name, website, industry, description, created_at, updated_at |
| Lead | id, client_id (FK Client, indexed), name, email, source, status, lead_score, created_at |
| Campaign | id, client_id (FK Client, indexed), campaign_name, platform, objective, budget, status, created_at |
| Content | id, client_id (FK Client, indexed), title, platform, content_type, body, status, scheduled_at, created_at |
| Report | id, client_id (FK Client, indexed), report_name, report_type, report_data, created_at |

One User owns many Clients. Each Client has many Leads, Campaigns, Content items, and Reports. Authorization must join child records through Client.user_id to the authenticated user. Use Decimal for monetary budgets, UTC timestamps, validated status values and score ranges, database constraints, and enabled SQLite foreign keys. Deletion behavior will be explicit and tested before client deletion ships.

Use portable SQLAlchemy types and Alembic migrations to keep a future PostgreSQL migration practical. Store no plaintext passwords and no OpenAI keys in these records.
