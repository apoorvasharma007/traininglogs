# Development Process Map

Quick reference for where everything lives and how to navigate.

---

## 📍 "I Want To..." Quick Navigation

### "I want to understand the current status"
1. Read: [DEV_STATUS.md](DEV_STATUS.md) (This document) ← START HERE
2. Then: [docs/tasks/PHASE6_READY.md](docs/tasks/PHASE6_READY.md)

### "I want to understand the architecture"
1. [docs/architecture.md](docs/architecture.md) — System design (10 min)
2. [docs/database.md](docs/database.md) — Data model (10 min)
3. [docs/session_flow.md](docs/session_flow.md) — User workflow (10 min)

### "I want to know how to code in this project"
1. [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md) — Standards (15 min)
2. [.agent/PROTOCOL.md](.agent/PROTOCOL.md) — Agent rules (10 min)
3. [CONTRIBUTING.md](CONTRIBUTING.md) — Workflow (10 min)

### "I want to see what to build next"
1. [docs/tasks/TASKLIST.md](docs/tasks/TASKLIST.md) — Complete roadmap
2. [docs/tasks/PHASE6.md](docs/tasks/PHASE6.md) — Current phase details
3. [.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md) — Next task spec

### "I want to start implementing Task 6.1"
1. Read spec: [.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md) (5 min)
2. Read standards: [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md) (10 min)
3. Review current code: [src/cli/main.py](src/cli/main.py) (10 min)
4. Implement (20 min)
5. Test: `python scripts/init_db.py && python -m src.cli.main`
6. Verify: `python .agent/scripts/verify_changes.py`
7. Commit with format: `[Task 6.1] Brief description`

### "I want to run the code"
```bash
# Initialize database
python scripts/init_db.py

# Run CLI
python -m src.cli.main

# Verify safety
python .agent/scripts/verify_changes.py
```

### "I want to understand commit message conventions"
Format:
```
[Task #N] Brief description

Detailed explanation of changes.
Task: Task 6.1
Tested: (what was tested)
```

See: [DEV_STATUS.md#commit-message-conventions](DEV_STATUS.md#-commit-message-conventions)

### "I have questions about how agents work"
→ [.agent/README.md](.agent/)

### "I want to understand the full requirements"
→ [docs/tasks/PHASE6.md](docs/tasks/PHASE6.md) (acceptance criteria per task)

---

## 📊 Development Process Flow

```
┌─────────────────────────────────────────────────────────────┐
│ START: Understand Current Status                           │
│ READ: DEV_STATUS.md                                         │
└────────────┬────────────────────────────────────────────────┘
             │
             ├─► "What's the big picture?"
             │   └─► docs/tasks/PHASE6_READY.md
             │       docs/tasks/TASKLIST.md
             │
             ├─► "What's the architecture?"
             │   └─► docs/architecture.md
             │       docs/database.md
             │       docs/session_flow.md
             │
             ├─► "How should I code?"
             │   └─► docs/development/CODEBASE_RULES.md
             │       .agent/PROTOCOL.md
             │       CONTRIBUTING.md
             │
             └─► "What should I build?"
                 └─► docs/tasks/PHASE6.md
                     .agent/workflows/phase_6_1.md
                     
┌─────────────────────────────────────────────────────────────┐
│ IMPLEMENTATION: Build the Feature                           │
│ FILES: src/cli/main.py, src/core/exercise_builder.py       │
│ REFERENCE: .agent/workflows/phase_6_1.md (detailed spec)    │
│ RULES: docs/development/CODEBASE_RULES.md                  │
└────────────┬────────────────────────────────────────────────┘
             │
             ├─► WRITE CODE (follow CODEBASE_RULES.md)
             │
             ├─► RUN TESTS
             │   └─► python scripts/init_db.py
             │       python -m src.cli.main
             │
             ├─► VERIFY SAFETY
             │   └─► python .agent/scripts/verify_changes.py
             │
             └─► COMMIT
                 └─► Format: [Task #N] description
                     Message: docs/commit conventions (above)

┌─────────────────────────────────────────────────────────────┐
│ REVIEW: Verify Against Standards                            │
│ CHECKLIST: docs/tasks/HUMAN_REVIEW_GUIDE.md                │
└────────────┬────────────────────────────────────────────────┘
             │
             ├─► Code follows CODEBASE_RULES.md
             ├─► No circular imports
             ├─► Database still initializes
             ├─► CLI launches
             ├─► Docstrings updated
             └─► TASKLIST.md marked as complete

┌─────────────────────────────────────────────────────────────┐
│ NEXT: Move to Task 6.2                                      │
│ REPEAT: Start at "What should I build?" above               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📚 Document Index

### Status & Planning
| Document | Purpose | Read Time |
|----------|---------|-----------|
| [DEV_STATUS.md](DEV_STATUS.md) | **START HERE** — Status, workflow, standards | 15 min |
| [docs/tasks/PHASE6_READY.md](docs/tasks/PHASE6_READY.md) | Current phase status & verification | 10 min |
| [docs/tasks/PHASE6.md](docs/tasks/PHASE6.md) | Task details & acceptance criteria | 15 min |
| [docs/tasks/TASKLIST.md](docs/tasks/TASKLIST.md) | Complete roadmap (Phases 1-7) | 15 min |

### Architecture & Design
| Document | Purpose | Read Time |
|----------|---------|-----------|
| [docs/architecture.md](docs/architecture.md) | System design & layers | 10 min |
| [docs/database.md](docs/database.md) | Data model & schema | 10 min |
| [docs/session_flow.md](docs/session_flow.md) | User interaction workflow | 10 min |

### Standards & Guidelines
| Document | Purpose | Read Time |
|----------|---------|-----------|
| [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md) | Coding standards & module rules | 15 min |
| [.agent/PROTOCOL.md](.agent/PROTOCOL.md) | Agent governance & safety | 15 min |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow | 10 min |

### Task Specifications
| Document | Purpose | Read Time |
|----------|---------|-----------|
| [.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md) | Task 6.1 implementation spec | 10 min |
| [docs/tasks/AUTONOMOUS_CODING_LOOP.md](docs/tasks/AUTONOMOUS_CODING_LOOP.md) | Agent workflow | 10 min |
| [docs/tasks/HUMAN_REVIEW_GUIDE.md](docs/tasks/HUMAN_REVIEW_GUIDE.md) | Code review checklist | 10 min |

---

## 🎯 Recommended Reading Order

### For Getting Started (30 minutes)
1. **[DEV_STATUS.md](DEV_STATUS.md)** (10 min) — Where we are, how to run code
2. **[docs/tasks/PHASE6_READY.md](docs/tasks/PHASE6_READY.md)** (10 min) — Next immediate steps
3. **[docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)** (10 min) — How to code

### For Full Context (90 minutes)
1. **[DEV_STATUS.md](DEV_STATUS.md)** (10 min)
2. **[docs/architecture.md](docs/architecture.md)** (10 min)
3. **[docs/database.md](docs/database.md)** (10 min)
4. **[docs/session_flow.md](docs/session_flow.md)** (10 min)
5. **[docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)** (15 min)
6. **[.agent/PROTOCOL.md](.agent/PROTOCOL.md)** (15 min)
7. **[docs/tasks/PHASE6.md](docs/tasks/PHASE6.md)** (15 min)

### For Implementing (90 minutes + coding)
1. **[.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md)** (10 min) — Spec
2. **[docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)** (10 min) — Rules
3. Review code: **[src/cli/main.py](src/cli/main.py)** (20 min)
4. Implement Task 6.1 (35 min)
5. Test & verify (15 min)

---

## 🔍 Where to Find Specific Information

### "Where are all the code files?"
→ [src/](src/) directory

### "Where are all the documentation files?"
→ [docs/](docs/) directory (+ [.agent/](.agent/) for governance)

### "Where are all the task files?"
→ [docs/tasks/](docs/tasks/) directory

### "How do I initialize the database?"
→ `python scripts/init_db.py`

### "How do I run the CLI?"
→ `python -m src.cli.main`

### "What are the coding rules?"
→ [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)

### "What's the commit message format?"
→ [DEV_STATUS.md#commit-message-conventions](DEV_STATUS.md#-commit-message-conventions)

### "How do agents work?"
→ [.agent/PROTOCOL.md](.agent/PROTOCOL.md)

### "What's the next task to build?"
→ [.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md)

### "How do I review code?"
→ [docs/tasks/HUMAN_REVIEW_GUIDE.md](docs/tasks/HUMAN_REVIEW_GUIDE.md)

---

## ⚡ Quick Commands

```bash
# Run database initialization
python scripts/init_db.py

# Run the CLI application
python -m src.cli.main

# Test imports (verify no circular deps)
python -c "from src.cli.main import main; print('✓ OK')"

# Safety verification
python .agent/scripts/verify_changes.py

# Check code style (if linting tools installed)
ruff check --line-length=88 src/
black --line-length=88 --check src/
```

---

## 📺 At a Glance

**Current Phase:** Phase 6 (Integration & Testing)  
**Status:** Ready to start building  
**Next Task:** [Task 6.1 - HistoryService Integration](.agent/workflows/phase_6_1.md)  
**Estimated Time:** 20 min implementation + 15 min testing  
**Code Standard:** [CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)  
**Commit Format:** `[Task #N] Description`  

---

**Start here:** [↑ DEV_STATUS.md](DEV_STATUS.md)
