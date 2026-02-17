````markdown
# Migration Log

## Version 1 (Current)

Initial traininglogs database schema for v1.

**Tables:**
- `schema_version`: Tracks database schema version
- `training_sessions`: Stores complete training session data as JSON

**Schema:**

```sql
CREATE TABLE training_sessions (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    phase TEXT,
    week INTEGER,
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY
);

CREATE INDEX idx_training_date ON training_sessions(date);
CREATE INDEX idx_training_phase ON training_sessions(phase);
CREATE INDEX idx_training_week ON training_sessions(week);
```

**When to migrate:**
- Initialize database: `python scripts/init_db.py`
- Check version: `python scripts/init_db.py` will show current schema version

---

## Version 2 (Future)

_Not yet implemented. When adding schema changes, document here._

**Planned changes:**
- (TBD) Example: Add exercises index table for faster exercise history queries

**Migration steps:**
1. Backup database: `cp traininglogs.db traininglogs.db.backup`
2. Run manual SQL:
   ```sql
   CREATE TABLE exercises (
       id TEXT PRIMARY KEY,
       session_id TEXT NOT NULL,
       name TEXT NOT NULL,
       ... (more columns)
       FOREIGN KEY(session_id) REFERENCES training_sessions(id)
   );
   ```
3. Update `migrations.py` with upgrade logic
4. Run `python scripts/init_db.py` to verify

---

## Migration Protocol

All schema changes must:
1. Be documented here BEFORE implementation
2. Include manual SQL steps
3. Include data migration logic (if needed)
4. Update `migrations.py` with upgrade path
5. Update `CURRENT_VERSION` in `migrations.py`

Backwards compatibility is not required for v1, but document breaking changes.

---

## Rollback Instructions

To rollback to previous version:
1. Stop any running CLI processes
2. Restore from backup: `cp traininglogs.db.backup traininglogs.db`
3. Verify: `python scripts/init_db.py`

No automatic rollback function provided; manual restoration required.

````
