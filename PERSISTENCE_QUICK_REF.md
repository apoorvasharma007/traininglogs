# Quick Persistence Reference

## Every Session Creates TWO Files

When user saves a workout session:

```
SESSION SAVED AUTOMATICALLY TO:

1. traininglogs.db (SQLite Database)
   └─ Location: /Users/apoorvasharma/local/traininglogs/
   └─ Size: ~28KB (grows with each session)
   └─ Purpose: Efficient queries, history lookups, analytics
   └─ Opened by: HistoryService, BasicQueries, Repository

2. training_session_YYYY_MM_DD_XXXX.json (Human-readable JSON)
   └─ Location: /Users/apoorvasharma/local/traininglogs/data/output/sessions/
   └─ Size: ~900 bytes per session
   └─ Purpose: Permanent, portable, readable records
   └─ Opened by: Text editors, Python json module, web browsers
```

## Verify Data Is Saved

### Check Database
```bash
ls -lh traininglogs.db
# Should show file ~28KB or larger with each session
```

### Check JSON Files
```bash
ls -la data/output/sessions/
# Should show training_session_*.json files

cat data/output/sessions/training_session_*.json | python3 -m json.tool
# Pretty-print JSON to see workout data
```

## View Session Data

### Open JSON File in Editor
```bash
# Visual inspection
open data/output/sessions/training_session_2026_02_16_3fcb25c2.json

# Or terminal
cat data/output/sessions/training_session_2026_02_16_3fcb25c2.json
```

### Query Database (Python)
```python
from persistence import get_database, TrainingSessionRepository
db = get_database()
repo = TrainingSessionRepository(db)
sessions = repo.get_all_sessions()
print(f"Total sessions saved: {len(sessions)}")
```

## Directory Structure

```
traininglogs/
├── traininglogs.db          ← SQLite database (28KB+)
├── data/
│   └── output/
│       ├── schemas/         ← Schema definitions
│       └── sessions/        ← JSON files (new with each save!)
│           ├── training_session_2026_02_16_3fcb25c2.json
│           ├── training_session_2026_02_17_a1b2c3d4.json
│           └── ... more files ...
└── src/
    ├── cli/
    ├── core/
    └── persistence/
        └── exporter.py      ← Handles JSON export
```

## Flow Diagram

```
User Logs Workout
       ↓
SessionManager.persist_session()
       ├─→ Save to DATABASE
       │   └─ traininglogs.db ✅
       └─→ Export to JSON FILE
           └─ data/output/sessions/*.json ✅
       ↓
CLI shows confirmation:
"Files written:
 • Database: traininglogs.db
 • JSON file: data/output/sessions/training_session_*.json"
```

## Backup & Recovery

### Backup Sessions
```bash
# Backup JSON files (recommended)
cp -r data/output/sessions/ sessions_backup/

# Or compress
tar -czf sessions_backup_$(date +%Y%m%d).tar.gz data/output/sessions/
```

### If Database Corrupts
```bash
# Database corrupted but JSON files safe!
rm traininglogs.db

# Reinitialize database
python scripts/init_db.py

# Phase 6.3 will support reimporting from JSON
```

## Implementation Details

### What Gets Exported to JSON
- Session metadata (date, phase, week, focus)
- All exercises with warmup and working sets
- Weight, reps, RPE, notes for each set
- Complete history for analysis

### JSON Schema
Matches `data/output/schemas/training_session_log_schema.jsonc`
```
{
  "dataModelVersion": "0.0.1",
  "_id": "session-uuid",
  "date": "ISO-8601 timestamp",
  "phase": 2,
  "week": 5,
  "focus": "upper-strength",
  "exercises": [...]
}
```

### File Naming
`training_session_YYYY_MM_DD_XXXXXXXX.json`
- YYYY_MM_DD = Session date
- XXXXXXXX = First 8 chars of session UUID

---

## Key Point

**Your data is now persisted in TWO places automatically:**

1. **Database** - For efficient querying and analytics
2. **JSON Files** - For human-readable, portable, permanent records

**You never have to worry about losing data to database corruption.**
