# traininglogs CLI

Interactive command-line workout logging system with SQLite persistence.

Build phase: **Phase 6 Ready** (Autonomous loop system operational)

---

## 🚀 Start Here

### **Phase 6 is ready to execute.**

📖 **Developer Getting Started:** Read [DEV_STATUS.md](DEV_STATUS.md) first! (10 min)
- Where we are in development
- How work is tracked
- How to run the code
- Standards & guidelines
- Next steps (Task 6.1 implementation)

For project overview: [docs/tasks/PHASE6_READY.md](docs/tasks/PHASE6_READY.md)

**TL;DR:** All infrastructure built. Ready for first agent task (Task 6.1 — HistoryService integration). ~20 min implementation + 15 min testing.

---

## Overview

A fast, lightweight CLI for logging training sessions with:
- ✅ Interactive prompts for session metadata and exercises
- ✅ SQLite-backed persistence (full JSON storage)
- ✅ Exercise history tracking (view last occurrence while logging)
- ✅ Structured validation maintaining datamodel integrity
- ✅ Agent-driven development approach with safety gates

**Project Goal:** Personal use only. Local CLI. No external LLM dependency in runtime.

---

## Completion Status

```
Phase 1: Foundation (Database layer)     ✅ COMPLETE
Phase 2: Core Logic (Business rules)     ✅ COMPLETE
Phase 3: History Service (Queries)       ✅ COMPLETE
Phase 4: Analytics (Aggregations)        ✅ COMPLETE
Phase 5: Governance (Docs + standards)   ✅ COMPLETE
Phase 6: Integration & Testing           🚀 READY
Phase 7+: Scaling & Optimization         📅 Planned
```

**Total Delivered:** 30+ files, 2,500+ lines of logic, 4,000+ lines of documentation, safety verification script, agent governance protocol.

---

## Quick Start

### 1. Initialize Database

```bash
python scripts/init_db.py
```

Creates `traininglogs.db` with schema.

**Optional:** Specify custom database path:
```bash
python scripts/init_db.py --db-path /path/to/custom.db
```

### 2. Run CLI (Coming in Phase 2)

```bash
python -m cli.main
```

---

## Architecture

```
CLI Layer (interactive prompts)
    ↓
Session Manager (in-memory session state)
    ↓
Exercise Builder (prompt-based set builder)
    ↓
Validation Layer (business rules enforcement)
    ↓
Persistence Layer (SQLite + JSON hybrid)
    ↓
History Service (previous exercise lookup)
```

---

## Folder Structure

```
traininglogs/
├── data_class_model/          # Existing datamodel (unchanged)
├── parser/                     # Existing parser (unused in v1)
├── cli/                        # CLI entry points
├── core/                       # Business logic (Session Manager, Exercise Builder)
├── persistence/                # Database access layer
├── history/                    # Exercise history service
├── analytics/                  # Query helpers
├── config/                     # Settings management
├── scripts/                    # Initialization scripts
├── docs/                       # Architecture documentation
├── agents/                     # Agent governance files
├── MIGRATIONS.md               # Database migration log
├── AGENT_PROTOCOL.md           # Agent workflow rules
├── CODEBASE_RULES.md           # Code standards
├── TASKLIST.md                 # Development roadmap
└── traininglogs.db             # SQLite database (gitignored)
```

---

## Database

**File:** `traininglogs.db` (SQLite 3)

**Main Table:**

```sql
CREATE TABLE training_sessions (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    phase TEXT,
    week INTEGER,
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_training_date ON training_sessions(date);
CREATE INDEX idx_training_phase ON training_sessions(phase);
CREATE INDEX idx_training_week ON training_sessions(week);
```

See [MIGRATIONS.md](MIGRATIONS.md) for schema version tracking and upgrade procedures.

---

## 📚 Master Index

### Get Started (5-15 minutes)

| Goal | Document | Time |
|------|----------|------|
| **Understand Phase 6** | [PHASE6_READY.md](PHASE6_READY.md) | 5 min |
| **Quick Phase 6 reference** | [OPTION_A_QUICK_START.md](OPTION_A_QUICK_START.md) | 5 min |
| **How to review agent code** | [HUMAN_REVIEW_GUIDE.md](HUMAN_REVIEW_GUIDE.md) | 10 min |

### Execute Phase 6 (20-30 minutes each task)

| Phase | Task | Document | Time |
|-------|------|----------|------|
| **6.1** | Integrate HistoryService | [.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md) | 20 min |
| **6.2** | Analytics CLI subcommand | [PHASE6.md](PHASE6.md) (section 6.2) | 40 min |
| **6.3** | Error handling | [PHASE6.md](PHASE6.md) (section 6.3) | 30 min |
| **6.4** | E2E manual testing | [PHASE6.md](PHASE6.md) (section 6.4) | 30 min |

### Deep Dives (15-20 minutes each)

| Topic | Document | Purpose |
|-------|----------|---------|
| **System Architecture** | [docs/architecture.md](docs/architecture.md) | Understand layers & data flow |
| **Database Design** | [docs/database.md](docs/database.md) | Schema, indices, JSON storage |
| **Session Workflow** | [docs/session_flow.md](docs/session_flow.md) | User flow, state machine |
| **Autonomous Loop Design** | [AUTONOMOUS_CODING_LOOP.md](AUTONOMOUS_CODING_LOOP.md) | Scaling strategy, architecture principles |

### Standards & Governance (10-15 minutes each)

| Topic | Document | Purpose |
|-------|----------|---------|
| **Code Standards** | [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md) | Module responsibilities, import rules |
| **Agent Protocol** | [.agent/PROTOCOL.md](.agent/PROTOCOL.md) | Agent roles, constraints, workflows |
| **Database Migrations** | [docs/development/MIGRATIONS.md](docs/development/MIGRATIONS.md) | Schema versioning, upgrade procedures |
| **Development Roadmap** | [TASKLIST.md](TASKLIST.md) | Complete phase breakdown |

### Tools & Scripts

| Tool | Path | Purpose |
|------|------|---------|
| **Safety Verification** | [.agent/scripts/verify_changes.py](.agent/scripts/verify_changes.py) | Automated safety checks (imports, DB, format) |
| **Database Init** | [scripts/init_db.py](scripts/init_db.py) | Initialize SQLite schema |
| **Analytics CLI** | `scripts/analytics.py` | Query training data (Phase 6.2) |

---

## Development Roadmap

See [TASKLIST.md](TASKLIST.md) for complete phase-by-phase plan.

**Currently executing:** Phase 6 — Integration & Testing

Each task is documented in PHASE6.md with:
- ✅ Detailed implementation steps
- ✅ Code examples and before/after
- ✅ Testing procedures and expected output
- ✅ Definition of done checklist

---

## Datamodel Reference

The `data_class_model/` directory contains comprehensive training session models:

- `TrainingSession` — Top-level session with metadata and exercises
- `Exercise` — Single exercise with warmup sets and working sets
- `WorkingSet` / `WarmupSet` — Per-set data with weight, reps, RPE
- `RepCount` — Full and partial rep tracking
- `Goal` — Planned targets for comparison
- `FailureTechnique` — Advanced techniques (MyoReps, LLP, Static, DropSet)
- `RepQualityAssessment` — Rep quality enum (good, bad, perfect, learning)

**Serialization:**
- All models have `to_dict()` → JSON and `from_dict()` → object methods
- Empty lists and None values are omitted from output
- Validation rules enforced on initialization

See `data_class_model/models.py` for full documentation.

---

## How to Extend

### Adding New Features

1. Check [TASKLIST.md](TASKLIST.md) for assigned phase
2. Review [CODEBASE_RULES.md](CODEBASE_RULES.md)
3. Follow [AGENT_PROTOCOL.md](AGENT_PROTOCOL.md) if using AI coding assistance

### Adding Database Fields

1. Update schema migration in [MIGRATIONS.md](MIGRATIONS.md)
2. Add migration logic to `persistence/migrations.py`
3. Update `persistence/database.py` if adding new table
4. Test: `python scripts/init_db.py`

### Adding New Queries

1. Add to `persistence/repository.py` if reading/writing sessions
2. Add to `analytics/basic_queries.py` if adding analytics
3. Document return types and parameters

---

## iPhone/Mobile Execution (Future)

Currently supports:
- ✅ Local macOS/Linux development
- ✅ Python 3.8+

Future options (not yet implemented):
1. **Pythonista app** — Python IDE on iOS
2. **iSH** — Linux shell environment on iOS
3. **SSH remote** — Run on server, access via phone
4. **Fast API wrapper** — REST API (Phase 6+)

---

## Development Standards

**No overengineering.** Simple solutions only.

- **Linting:** `ruff` (line length: 88)
- **Formatting:** `black` (line length: 88)
- **Type hints:** Lightweight, not strict
- **CI:** None (manual testing only)
- **Database:** No ORM, raw SQLite with migrations

See [CODEBASE_RULES.md](CODEBASE_RULES.md) for governance.

---

## Troubleshooting

**Database schema mismatch:**
```
⚠️  Schema version mismatch!
   Database version: X
   Expected version: Y
```
→ See [MIGRATIONS.md](MIGRATIONS.md) for upgrade steps.

**Import errors:**
```
ModuleNotFoundError: No module named 'persistence'
```
→ Run from project root: `python -m cli.main`

---

## Contributing

This project uses an agent-assisted development workflow.

- Implementation: Use `builder_agent.md`
- Refactoring: Use `refactor_agent.md`
- Migrations: Use `migration_agent.md`
- Analytics: Use `analytics_agent.md`

See [AGENT_PROTOCOL.md](AGENT_PROTOCOL.md) for full protocol.

---

## License

Personal project. Closed use.

