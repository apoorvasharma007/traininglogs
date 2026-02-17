# TASKLIST.md

Development roadmap for traininglogs CLI.

Status: **Phase 5 — Governance (In Progress)**

---

## Phase 1 — Foundation ✅

Database and data persistence layer.

- ✅ Task 1.1: Create folder structure
- ✅ Task 1.2: Implement database.py (SQLite connection, schema init)
- ✅ Task 1.3: Implement migrations.py (version tracking)
- ✅ Task 1.4: Implement repository.py (CRUD operations)
- ✅ Task 1.5: Create init_db.py (database initialization script)
- ✅ Task 1.6: Add migration version table and tracking
- ✅ Task 1.7: Update README with DB setup instructions

---

## Phase 2 — Core Logic ✅

Business logic and user interaction foundation.

- ✅ Task 2.1: Implement SessionManager
  - Session start/add/finish/cancel/persist
  - In-memory state management
  - Repository integration

- ✅ Task 2.2: Implement ExerciseBuilder
  - Interactive prompt-based exercise construction
  - Warmup and working set input
  - RPE and rep quality capture

- ✅ Task 2.3: Implement Validators
  - Weight, reps, week, RPE validation
  - Session-level validation
  - Set data validation

- ✅ Task 2.4: Wire CLI Layer
  - Create cli/main.py (application entry point)
  - Create cli/prompts.py (user interface)
  - Orchestrate workflow: session → exercises → validation → save

---

## Phase 3 — History ✅

Previous exercise tracking and reference.

- ✅ Task 3.1: Implement HistoryService
  - get_last_exercise(name)
  - get_exercise_history(name, limit)
  - get_last_weight_and_reps(name)
  - get_average_weight(name)
  - get_exercise_progression(name)

- ⏳ Task 3.2: Integrate HistoryService into CLI
  - Show previous exercise data while building exercise
  - Display in ExerciseBuilder prompts
  - *Note: Not yet integrated into main.py workflow*

---

## Phase 4 — Analytics ✅

Queries and reports on training data.

- ✅ Task 4.1: Implement BasicQueries
  - get_last_n_sessions(n)
  - get_sessions_in_phase(phase)
  - get_total_volume(session)
  - get_exercise_volume(exercise)
  - get_weekly_volume(phase, week)
  - get_exercise_frequency(name)

- ✅ Task 4.2: Add formatted display methods
  - show_last_5_sessions()
  - show_exercise_history(name)
  - show_weekly_volume(phase, week)

- ⏳ Task 4.3: Create analytics CLI commands
  - New subcommand: `python -m cli.analytics --last-sessions 5`
  - *Note: Not yet implemented*

---

## Phase 5 — Governance ✅

Documentation and agent protocols.

- ✅ Task 5.1: Create CODEBASE_RULES.md
  - Module responsibilities
  - Naming conventions
  - Import rules
  - Code style

- ✅ Task 5.2: Create AGENT_PROTOCOL.md
  - Builder agent guidelines
  - Refactor agent guidelines
  - Migration agent guidelines
  - Analytics agent guidelines
  - Safety checks and feedback loops

- ✅ Task 5.3: Create architecture documentation
  - docs/architecture.md
  - docs/database.md
  - docs/session_flow.md

- ✅ Task 5.4: Update MIGRATIONS.md with version tracking
  - Initial schema documentation
  - Migration protocol

- ⏳ Task 5.5: Create __init__.py files for all packages
  - *Partially done, may need verification*

---

## Phase 6 — Integration & Testing

CLI enhancements and quality assurance.

- ⏳ Task 6.1: Integrate HistoryService into ExerciseBuilder
  - Show previous exercise while adding current
  - Suggest weight/reps based on history

- ⏳ Task 6.2: Add analytics subcommand
  - CLI command: `python -m cli.analytics`
  - List options: sessions, exercise history, volume

- ⏳ Task 6.3: Error handling and edge cases
  - Empty database
  - Missing phase/week
  - Invalid inputs recovery

- ⏳ Task 6.4: Manual testing
  - Full workflow: init → log session → view history
  - Analytics queries
  - Database persistence

---

## Phase 7 — iOS/Mobile Strategy

Documentation for future mobile execution.

- ⏳ Task 7.1: Document Pythonista support
  - File structure access
  - SQLite in Pythonista

- ⏳ Task 7.2: Document iSH support
  - Linux environment setup
  - Python installation

- ⏳ Task 7.3: Document SSH remote option
  - Run on server, access via phone
  - Port forwarding

- ⏳ Task 7.4: Evaluate FastAPI wrapper (Phase 8+)
  - REST API layer
  - Web dashboard
  - Mobile app backend

---

## Phase 8+ — Future (Not Scheduled)

Advanced features for future iterations.

- 🔮 LLM shorthand input parsing
  - "bench 80x5 rpe 8" as input shorthand
  - Natural language to set data

- 🔮 Voice interface
  - Audio input for logging
  - Voice output for history

- 🔮 REST API layer
  - FastAPI wrapper
  - Remote access

- 🔮 Web dashboard
  - Session viewer
  - Progress charts
  - Analytics dashboard

- 🔮 Mobile app
  - Native iOS/Android
  - Offline sync

---

## Current State

**Completed:** Phases 1-5 (Foundation, Core, History, Analytics, Governance)  
**Status:** Phase 6 Ready for Human-in-the-Loop Builder Agent  
**Next:** Phase 6.1 (Integrate HistoryService into CLI)

👉 **START HERE:** [OPTION_A_QUICK_START.md](OPTION_A_QUICK_START.md)

📋 **Phase 6 Tasks:** [PHASE6.md](PHASE6.md)

---

## How to Use This List

1. **For Builder Agent:** Pick next task from current phase
2. **For Human Developer:** Use ✅ to track completion
3. **To Update:** Mark task completion and increment phase status
4. **For Priority:** Focus on Phase 6-7 for immediate improvement

---

## Notes

- Database is SQLite with JSON storage (no ORM)
- No AI in runtime (only for development)
- Personal use only, no authentication
- Agent-assisted development workflow in place
