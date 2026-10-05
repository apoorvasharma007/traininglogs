# Changing what the database stores

Use this when the database needs to hold something new, like a new field on a set or a new
table.

1. Write the change in `src/traininglogs/db/schema.sql`. Only add things: a new column or a new
   table. Never rename or delete in place, because existing data and the API depend on those
   names. A change that has to rename or restructure goes through a migration script instead, as
   `scripts/migrate_to_accounts.py` did: one transaction, a dry run by default, counts compared
   old against new.

   A new table follows the design in `db-redesign-plan.md`: `id UUID PRIMARY KEY` made by
   `db/ids.py` (never built from data or chosen by the phone); `user_id UUID NOT NULL`, unless it's
   shared reference data; `UNIQUE (user_id, id)`; a child points at its parent by
   `FOREIGN KEY (user_id, parent_id) REFERENCES parent(user_id, id)`; indexes lead with `user_id`;
   `ENABLE ROW LEVEL SECURITY` at the end of the file; and a test in
   `tests/test_accounts_schema.py` if it adds a rule.

2. Add a new column as its own line, `ALTER TABLE <table> ADD COLUMN IF NOT EXISTS ...`, not only
   inside the `CREATE TABLE` block. A database that already exists skips the `CREATE TABLE` block
   entirely, so a column written only there never reaches it. Four columns in prod went missing
   this way.

3. Run the tests. They apply `schema.sql` to the test database every time, so a broken change
   fails there first.

4. Before touching prod, look first. Compare prod's tables and columns with `schema.sql` and list
   exactly what's missing. Looking changes nothing.

5. Show Apoorva the exact SQL that adds the missing pieces, and wait for a yes. A yes from an
   earlier session doesn't count.

6. Run it as one block that either fully succeeds or changes nothing, in the foreground. Count the
   rows in every table before and after. If any count moved when it shouldn't have, undo it.

If a change would have to rewrite rows that are already there, stop and plan it with Apoorva
first. Take a backup into `backups/` before anything runs.
