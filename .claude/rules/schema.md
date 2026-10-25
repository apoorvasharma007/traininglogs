---
paths:
  - "src/traininglogs/db/migrations/**"
  - "src/traininglogs/db/db.py"
  - "src/traininglogs/models/**"
  - "src/traininglogs/api/schemas.py"
  - "scripts/migrate*"
---

# Changing what the database stores

- A change to the tables' shape is a new schema change file in `src/traininglogs/db/migrations/`,
  numbered one past the highest: `0002_add_library_exercise_id.sql`. Never edit a file that has
  run on staging or production; `db.py` refuses one whose text changed after it ran. Why: each
  database runs each file once, so an edit reaches only databases that haven't run it yet.
- Add first, drop after: a file that drops or renames something the deployed code still reads goes
  in a file of its own, run after the deploy (`0003_drop_replaced_columns.sql`). The adding file
  runs before it. Why: staging and production run `dev`'s and `main`'s code while their schema
  changes by hand, so a drop that runs first breaks the live app until the deploy lands.
- A rename, a removal or a restructure is planned with Apoorva first. Changing stored rows (a data
  migration) is a script of its own: one transaction, dry run by default, counts compared old
  against new, like `scripts/migrate_to_accounts.py`.
- Don't rename database columns or Pydantic fields unless asked. The API, the app and stored data
  depend on them.
- A new table follows `db-redesign-plan.md`: `id UUID PRIMARY KEY` from
  `src/traininglogs/db/ids.py`, `user_id UUID NOT NULL` unless it's shared reference data,
  `UNIQUE (user_id, id)`, children point at parents by `(user_id, parent_id)`, indexes lead with
  `user_id`, and row-level security enabled in the same file.
- Applying the files to staging or production is `scripts/migrate.py`: its dry run first, then
  `--apply`, following the production data rules in `CLAUDE.md`.
