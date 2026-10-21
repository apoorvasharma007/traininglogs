---
paths:
  - "src/traininglogs/db/schema.sql"
  - "src/traininglogs/models/**"
  - "src/traininglogs/api/schemas.py"
  - "scripts/migrate*"
---

# Changing what the database stores

- Schema changes only add: a new column or a new table. A rename or restructure is a migration
  script (one transaction, dry run by default, counts compared old against new, like
  `scripts/migrate_to_accounts.py`), planned with Apoorva first.
- A new column also gets its own `ALTER TABLE <table> ADD COLUMN IF NOT EXISTS ...` line. Why: an
  existing database skips the `CREATE TABLE` block, and four columns went missing in production
  this way.
- Don't rename database columns or Pydantic fields unless asked. The API, the app and stored data
  depend on them.
- A new table follows `db-redesign-plan.md`: `id UUID PRIMARY KEY` from
  `src/traininglogs/db/ids.py`, `user_id UUID NOT NULL` unless it's shared reference data,
  `UNIQUE (user_id, id)`, children point at parents by `(user_id, parent_id)`, indexes lead with
  `user_id`, and row-level security enabled at the end of the file.
- Applying a change to production follows the production data rules in `CLAUDE.md`.
