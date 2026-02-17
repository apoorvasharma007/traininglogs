# Architecture Overview

High-level system design for traininglogs CLI v1.

## System Layers

```
┌─────────────────────────────────────┐
│       CLI Layer (Prompts)            │
│   main.py, prompts.py                │
│   User interaction and navigation    │
├─────────────────────────────────────┤
│      Session Manager                 │
│   Orchestrates workflow              │
│   Maintains in-memory session state  │
├─────────────────────────────────────┤
│   Core Logic (Business Rules)        │
│   SessionManager, ExerciseBuilder    │
│   Validators                         │
├─────────────────────────────────────┤
│   History & Analytics (Read-only)    │
│   HistoryService, BasicQueries       │
├─────────────────────────────────────┤
│   Persistence Layer                  │
│   Repository (CRUD operations)       │
│   Database (SQLite connection)       │
├─────────────────────────────────────┤
│        SQLite Database               │
│   traininglogs.db                    │
│   training_sessions table (JSON)     │
└─────────────────────────────────────┘
```

## Data Flow

### Creating a Session

1. **CLI** → Ask user for metadata (phase, week, focus, deload)
2. **SessionManager** → Create in-memory session object
3. **CLI** → Loop: add exercises
4. **ExerciseBuilder** → Prompt for warmup/working sets
5. **HistoryService** → Retrieve previous exercise data (optional)
6. **SessionManager** → Add exercise to session
7. **CLI** → Show summary, confirm save
8. **SessionManager** → Validate complete session
9. **Repository** → Save session to database
10. **Database** → Write JSON record

### Retrieving History

1. **CLI** → Request exercise history
2. **HistoryService** → Query repository
3. **Repository** → Fetch sessions from database
4. **HistoryService** → Parse JSON, find matching exercise
5. **CLI** → Display previous data

### Running Analytics

1. **CLI** → Request analytics
2. **BasicQueries** → Query operations via repository
3. **Repository** → Fetch raw session data
4. **BasicQueries** → Aggregate and calculate
5. **CLI** → Display formatted results

## Module Responsibilities

### `cli/` — User Interface
- **main.py:** Application entry point, orchestrates workflow
- **prompts.py:** All user interaction (input/output)

No business logic here.

### `core/` — Business Logic
- **session_manager.py:** Session lifecycle (start, add exercise, finish, save)
- **exercise_builder.py:** Interactive exercise construction
- **validators.py:** All validation rules

No database access or user prompts here.

### `persistence/` — Data Access
- **database.py:** SQLite connection and schema management
- **migrations.py:** Schema version tracking
- **repository.py:** Query and write operations

No business logic here.

### `history/` — Exercise History
- **history_service.py:** Retrieve previous exercise data

Read-only operations only. Uses repository.

### `analytics/` — Data Analysis
- **basic_queries.py:** Aggregate queries and reports

Read-only operations only. Uses repository.

### `config/` — Configuration
- **settings.py:** Environment variables, app settings

Single source of truth.

### `scripts/` — Utilities
- **init_db.py:** Database initialization

Standalone scripts for admin tasks.

## Session Object Structure

```json
{
  "id": "uuid-string",
  "date": "2025-02-16T12:00:00",
  "phase": "phase 2",
  "week": 5,
  "focus": "upper-strength",
  "is_deload": false,
  "exercises": [
    {
      "name": "Barbell Bench Press",
      "warmup_sets": [
        {"weight_kg": 20, "full_reps": 5},
        {"weight_kg": 40, "full_reps": 3}
      ],
      "working_sets": [
        {
          "weight_kg": 80,
          "full_reps": 5,
          "partial_reps": 0,
          "rpe": 8,
          "rep_quality": "good"
        },
        {
          "weight_kg": 82.5,
          "full_reps": 5,
          "partial_reps": 1,
          "rpe": 10,
          "rep_quality": "perfect"
        }
      ]
    }
  ],
  "created_at": "2025-02-16T12:30:45"
}
```

## Dependency Rules

```
cli/         ← imports from core, persistence, history, analytics, config
             (orchestration layer)
             
core/        ← imports from persistence, config
             (business logic)
             
persistence/ ← imports only stdlib + config
             (data access layer)
             
history/     ← imports from persistence, config
             (read-only queries)
             
analytics/   ← imports from persistence, config
             (read-only queries)
             
config/      ← imports only stdlib
             (settings)
```

**No circular imports allowed.**

## Design Principles

1. **Separation of Concerns**
   - Presentation (CLI) separate from logic
   - Logic separate from persistence
   - Validation in one place

2. **Single Responsibility**
   - Each module has one reason to change
   - SessionManager owns session state
   - Repository owns database access

3. **Testability**
   - Logic can be tested without prompts
   - Database can be tested without CLI
   - Services are injectable via dependency injection

4. **Extensibility**
   - New queries add to BasicQueries
   - New validators add to validators.py
   - New CLI commands extend main.py

## Future Architecture Changes

Potential improvements (not in v1):

- **Exercise Index Table:** Currently searches all sessions for exercise history. Could add `exercises` table with foreign key to `training_sessions` for O(1) lookups.

- **User-specific Sessions:** Currently single-user. Adding `user_id` would enable multi-user.

- **API Layer:** FastAPI wrapper around core logic for remote access.

- **Caching:** In-memory cache of recent exercises for fast history lookup.

- **Event Logging:** Audit log of all writes for data recovery.

See TASKLIST.md for scheduled improvements.
