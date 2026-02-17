# Data Persistence Implementation ✅

## Overview

Every time a user completes a workout and saves it, the system now creates **permanent records** in two places:

1. **SQLite Database** (`traininglogs.db`) - For queries and analytics
2. **JSON Files** (`data/output/sessions/`) - For human-readable, portable records

This ensures data is never lost and can be accessed both programmatically and manually.

---

## Implementation Details

### Architecture

```
User logs workout via CLI
    ↓
SessionManager.persist_session()
    ↓
    ├─→ Repository.save_session()
    │   └─→ SQLite database write
    │       (for queries/analytics)
    │
    └─→ SessionExporter.export_session()
        └─→ JSON file write
            (for portable, readable records)
```

### What Gets Persisted

Every saved session includes:

**Metadata:**
- Session ID (UUID)
- Date/time
- Training phase and week
- Workout focus (e.g., "upper-strength")
- Deload flag

**Exercises:**
- Exercise name
- Warmup sets (weight, reps)
- Working sets (weight, reps, RPE)
- Notes and assessments

---

## Database Persistence

### File: `traininglogs.db`

**Location:** Root directory
**Format:** SQLite 3
**Purpose:** Efficient queries, history lookups, analytics

**Schema:**
```sql
CREATE TABLE training_sessions (
    id TEXT PRIMARY KEY,
    date TEXT,
    phase TEXT,
    week INTEGER,
    raw_json TEXT,
    created_at TEXT
)
```

**Accessed by:**
- HistoryService (queries previous exercises)
- BasicQueries (analytics)
- SessionManager (persistence)

### Example Query

```python
from persistence import TrainingSessionRepository, get_database

db = get_database()
repo = TrainingSessionRepository(db)

# Get last barbell bench press
sessions = repo.get_all_sessions()
for session in sessions:
    for exercise in session['exercises']:
        if exercise['name'] == 'Barbell Bench Press':
            print(f"Weight: {exercise['working_sets'][0]['weight']}kg")
```

---

## File-Based Persistence (NEW)

### File: `data/output/sessions/training_session_YYYY_MM_DD_XXXX.json`

**Location:** `data/output/sessions/`
**Format:** JSON with comments (matching schema)
**Purpose:** Permanent, readable, portable records

**Filename Convention:**
- `YYYY_MM_DD` = Session date
- `XXXX` = First 8 characters of session ID

**Example:**
```
training_session_2026_02_16_3fcb25c2.json
training_session_2026_02_17_a1b2c3d4.json
```

### JSON Structure

Matches the schema in `data/output/schemas/training_session_log_schema.jsonc`:

```json
{
  "dataModelVersion": "0.0.1",
  "dataModelType": "training_session_log",
  "_id": "session-uuid",
  "userId": "apoorva",
  "userName": "Apoorva Sharma",
  "date": "2026-02-16T23:34:50.722615",
  "phase": 2,
  "week": 5,
  "isDeloadWeek": false,
  "focus": "upper-strength",
  "exercises": [
    {
      "Order": 1,
      "Name": "Barbell Bench Press",
      "warmupSets": [...],
      "workingSets": [...]
    }
  ]
}
```

### Key Features

✅ **Human-Readable** - Can be opened in any text editor
✅ **Portable** - JSON is universal, not database-specific  
✅ **Schema-Compliant** - Matches official data schema
✅ **Complete Records** - Every field captured
✅ **Version Traceable** - Includes dataModelVersion

---

## Implementation Code

### SessionExporter Class

**File:** `src/persistence/exporter.py`

```python
class SessionExporter:
    """Exports training sessions to JSON files matching schema."""
    
    def export_session(self, session_data: Dict[str, Any]) -> str:
        """
        Export session to JSON file.
        
        Returns:
            Path to written file
        """
        # Transform data to schema format
        schema_data = self._transform_to_schema(session_data)
        
        # Write to file
        file_path = self.output_dir / filename
        with open(file_path, 'w') as f:
            json.dump(schema_data, f, indent=2)
        
        return str(file_path)
```

### SessionManager Integration

**File:** `src/core/session_manager.py`

```python
class SessionManager:
    def __init__(self, repository: TrainingSessionRepository):
        self.repository = repository
        self.exporter = SessionExporter()  # ← NEW
        
    def persist_session(self) -> bool:
        """Persist to DB AND export to JSON."""
        # Save to database
        self.repository.save_session(session_id, self.current_session)
        
        # Export to JSON file
        export_path = self.exporter.export_session(self.current_session)
        
        return True
```

### CLI Feedback

**File:** `src/cli/main.py`

```python
if prompts.confirm_save():
    session_manager.persist_session()
    
    # Show user where files were created
    prompts.show_success("Session saved! ✅")
    prompts.show_info("Files written:")
    prompts.show_info("  • Database: traininglogs.db")
    prompts.show_info("  • JSON file: data/output/sessions/training_session_*.json")
```

---

## Verification

### Check What Gets Persisted

**Database (SQLite):**
```bash
# Check if database exists
ls -lh traininglogs.db

# Query database (requires sqlite3 CLI)
sqlite3 traininglogs.db "SELECT COUNT(*) FROM training_sessions;"
```

**JSON Files:**
```bash
# List all session files
ls -la data/output/sessions/

# View specific session
cat data/output/sessions/training_session_2026_02_16_3fcb25c2.json

# Pretty-print JSON
cat data/output/sessions/training_session_2026_02_16_3fcb25c2.json | python3 -m json.tool
```

### Test Persistence

**Manual Test:**
```bash
# 1. Initialize database
python scripts/init_db.py

# 2. Run CLI and log a workout
python -m src.cli.main

# 3. Verify both files created
ls -l traininglogs.db data/output/sessions/

# 4. View the JSON file
cat data/output/sessions/training_session_*.json
```

---

## Data Flow

### Complete Session Lifecycle

```
1. USER STARTS CLI
   └─ SessionManager created
   └─ SessionExporter created

2. USER LOGS WORKOUT
   └─ SessionManager.start_session()
   └─ SessionManager.add_exercise() (repeat for each exercise)
   └─ SessionManager.finish_session()

3. USER CONFIRMS SAVE
   └─ SessionManager.persist_session()
       ├─→ Repository.save_session()
       │   └─→ SQLite INSERT
       │       └─→ DATA IN DATABASE ✅
       │
       └─→ SessionExporter.export_session()
           ├─→ Transform to schema
           └─→ Write JSON file
               └─→ DATA IN JSON FILE ✅

4. CONFIRMATION SHOWN TO USER
   └─ "Files written:"
   └─ "  • Database: traininglogs.db"
   └─ "  • JSON file: data/output/sessions/training_session_2026_02_16_3fcb25c2.json"

5. SESSION CLEARED FROM MEMORY
   └─ current_session = None
```

---

## Benefits

### Before This Implementation

```
User logs workout
    ↓
Data saved to database only
    ↓
Problem: If database corrupts, no recovery
Problem: Can't view raw data without code
Problem: Can't share data easily
```

### After This Implementation

```
User logs workout
    ↓
Data saved to DATABASE + JSON FILE
    ↓
✅ Redundancy - Data exists in two places
✅ Readability - JSON human-readable
✅ Portability - JSON works anywhere
✅ Recovery - If DB corrupts, JSON still accessible
✅ Sharing - Can send JSON files directly
✅ Analytics - Later phase can bulk-import from JSON
```

---

## File Organization

```
traininglogs/
├── traininglogs.db                          ← Database
├── data/
│   └── output/
│       ├── schemas/                         ← Schema definitions
│       │   └── training_session_log_schema.jsonc
│       └── sessions/                        ← Session JSON files (NEW)
│           ├── training_session_2026_02_16_3fcb25c2.json
│           ├── training_session_2026_02_17_a1b2c3d4.json
│           └── ... more sessions ...
└── src/
    └── persistence/
        ├── __init__.py
        ├── database.py                      ← SQLite connection
        ├── repository.py                    ← DB queries
        ├── migrations.py
        └── exporter.py                      ← JSON export (NEW)
```

---

## Accessing Data Later

### Using Python Code

```python
# Read from database
from persistence import get_database, TrainingSessionRepository
db = get_database()
repo = TrainingSessionRepository(db)
sessions = repo.get_all_sessions()

# Or read from JSON files
import json
from pathlib import Path

for json_file in Path('data/output/sessions').glob('*.json'):
    with open(json_file) as f:
        session = json.load(f)
        print(f"Session: {session['_id']}")
        print(f"Exercises: {len(session['exercises'])}")
```

### Using File System

```bash
# View all sessions
cat data/output/sessions/*.json | python3 -m json.tool

# Export specific date
ls data/output/sessions/training_session_2026_02_16_*.json

# Backup all sessions
tar -czf sessions_backup.tar.gz data/output/sessions/
```

---

## Next Steps

### Phase 6.2: Analytics Integration
- Query JSON files in addition to database
- Bulk statistics from multiple sessions
- Progress tracking visualization

### Phase 6.3: Data Import
- Read markdown files
- Convert to JSON format
- Bulk import into sessions directory
- Auto-load into database

### Phase 7: Cloud Sync (Future)
- Upload JSON files to cloud
- Sync across devices
- Backup system

---

## Troubleshooting

### Issue: JSON files not created

**Check:**
1. Directory exists: `mkdir -p data/output/sessions`
2. Write permissions: `ls -ld data/output/sessions`
3. Test with: `touch data/output/sessions/test.json`

### Issue: Database corrupted

**Recovery:**
```bash
# Delete database (sessions are safe in JSON!)
rm traininglogs.db

# Reinitialize
python scripts/init_db.py

# Reimport from JSON (coming in Phase 6.3)
# For now, can manually copy files to new database
```

### Issue: JSON file invalid

**Debug:**
```bash
# Validate JSON syntax
python3 -m json.tool data/output/sessions/training_session_*.json

# Check file size (should be 500+ bytes)
ls -lh data/output/sessions/training_session_*.json
```

---

## Summary

✅ **Dual Persistence:** Both database and JSON files  
✅ **Schema Compliance:** JSON matches official schema  
✅ **Human Readable:** Can open files in text editor  
✅ **Automatic Export:** Every save creates JSON file  
✅ **Permanent Records:** Never lose data to database corruption  
✅ **Portable:** JSON files can be backed up, shared, analyzed separately  

**Result:** Complete confidence that your training data is safe and accessible.
