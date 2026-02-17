# Database Schema & Design

SQLite database for traininglogs.

File: `traininglogs.db`

## Tables

### `training_sessions`

Stores complete training sessions as JSON.

```sql
CREATE TABLE training_sessions (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    phase TEXT,
    week INTEGER,
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | UUID session identifier |
| `date` | TEXT | Session date (ISO 8601) |
| `phase` | TEXT | Training phase (e.g., "phase 2") |
| `week` | INTEGER | Week number |
| `raw_json` | TEXT | Complete session data as JSON string |
| `created_at` | TEXT | Timestamp when record was created (ISO 8601) |

**Constraints:**
- `id` is primary key, unique
- `date` is not null
- `raw_json` is not null

### `schema_version`

Tracks database schema version for migrations.

```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY
);
```

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `version` | INTEGER | Current schema version |

**Current Version:** 1

## Indices

Fast lookups by date, phase, week:

```sql
CREATE INDEX idx_training_date ON training_sessions(date);
CREATE INDEX idx_training_phase ON training_sessions(phase);
CREATE INDEX idx_training_week ON training_sessions(week);
```

## Design Decisions

### JSON Storage (NoSQL Hybrid)

Why store full JSON instead of normalized schema?

**Pros:**
- ✅ Flexible schema — exercises, sets, and fields can evolve
- ✅ Atomic sessions — complete data or nothing
- ✅ Versioning-friendly — add new fields without migration
- ✅ Simple querying — single row per session
- ✅ Direct datamodel — SessionObject → JSON → Database

**Cons:**
- ❌ Can't query exercise details directly
- ❌ No foreign key constraints
- ❌ Larger storage per row
- ❌ Slower aggregation queries

### Metadata Columns

Why duplicate `phase`, `week` in SQL?

**Indexing:** Allows fast filters by phase/week without JSON parsing  
**Querying:** Build composite queries like "show all sessions in phase 2, week 5"

### Single `id` PrimaryKey

Why not auto-increment?

**Migration-friendly:** UUIDs survive database rebuilds  
**Multi-device:** If future mobile sync, UUIDs avoid conflicts

## JSON Structure Examples

See [TASKLIST.md > Session Object Structure](../docs/architecture.md#session-object-structure)

## Queries

### Retrieve Specific Session

```sql
SELECT raw_json FROM training_sessions WHERE id = 'uuid-here';
```

### List Sessions by Date

```sql
SELECT raw_json FROM training_sessions 
WHERE date = '2025-02-16'
ORDER BY created_at DESC;
```

### List Sessions by Phase

```sql
SELECT raw_json FROM training_sessions
WHERE phase = 'phase 2'
ORDER BY date DESC;
```

### List Sessions by Phase & Week

```sql
SELECT raw_json FROM training_sessions
WHERE phase = 'phase 2' AND week = 5
ORDER BY created_at DESC;
```

### Count Total Sessions

```sql
SELECT COUNT(*) FROM training_sessions;
```

### Get Last N Sessions

```sql
SELECT raw_json FROM training_sessions
ORDER BY date DESC, created_at DESC
LIMIT 10;
```

## Migration Strategy

See [docs/development/MIGRATIONS.md](../development/MIGRATIONS.md) for full migration protocol.

### Current Version: 1

**Schema:**
- Initial `training_sessions` table
- `schema_version` tracking
- Three indices (date, phase, week)

### Future: Version 2+

When adding schema changes:

1. Update `MIGRATIONS.md` with planned changes
2. Add migration logic to `persistence/migrations.py`
3. Implement `upgrade_to(2)` method
4. Increment `CURRENT_VERSION`
5. Document rollback procedure
6. Test init_db.py with new version

## Performance Notes

### Current O(n) Operations

**Exercise history lookup:**
```
get_last_occurrence_of_exercise(name)
→ SELECT all sessions (up to 50)
→ Parse JSON
→ Find matching exercise
```

**Performance:** O(n) scan + JSON parse

**Solution for large datasets (Phase 8+):**
- Add `exercises` table with foreign key
- Index by exercise name
- O(1) lookup

### Typical Query Times

With < 100 sessions:
- List last 5 sessions: < 10ms
- Filter by phase: < 5ms
- Get exercise history: < 20ms

With > 1000 sessions:
- List last 5 sessions: < 1ms (index)
- Filter by phase: < 10ms (index)
- Get exercise history: > 100ms (full scan)

## Backup & Recovery

### Manual Backup

```bash
cp traininglogs.db traininglogs.db.backup
```

### Restore from Backup

```bash
cp traininglogs.db.backup traininglogs.db
```

### SQL Dump (Text Backup)

```bash
sqlite3 traininglogs.db .dump > backup.sql
```

### Restore from SQL Dump

```bash
sqlite3 new_db.db < backup.sql
```

## Development & Testing

### Reset Database

```bash
rm traininglogs.db
python scripts/init_db.py
```

### Inspect Database

```bash
sqlite3 traininglogs.db
sqlite> SELECT COUNT(*) FROM training_sessions;
sqlite> .dump training_sessions LIMIT 1;
sqlite> .exit
```

### Current Size (Empty)

```
Schema + Indices: ~8KB
Per Session (avg): ~2-5KB (depending on exercise count)
```

## Constraints & Limitations

### Current Version Constraints

- Single user (no auth)
- No concurrent writes (non-multi-threaded)
- No data validation at SQLite level (app-side validation)
- No soft-delete (DELETE is hard delete)

### Not Supported (v1)

- ❌ Transactions across multiple API calls
- ❌ Referential integrity
- ❌ Triggers for audit log
- ❌ Full-text search on exercises

## Future Enhancements

See Phase 8+ in [TASKLIST.md](../TASKLIST.md).

Potential:
- Partition by phase/week for larger datasets
- Read replicas for analytics
- Event sourcing for audit trail
- Incremental backups
