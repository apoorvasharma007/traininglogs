The schema is numbered schema change files in `src/traininglogs/db/migrations/`, starting with
`0001_baseline.sql` (the old `schema.sql`). Each runs once per database, in order, and the new
`schema_migrations` table records which have run. `scripts/migrate.py` shows what a database is
missing and, with `--apply`, runs it.
