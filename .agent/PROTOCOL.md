````markdown
# AGENT_PROTOCOL.md

How to use AI agents for development on traininglogs.

This protocol enables safe, efficient agent-assisted development.

## Agent Roles

### Builder Agent
**Purpose:** Implement new features  
**File:** `.agent/roles/builder.md`

When using:
1. Only implement features listed in TASKLIST.md
2. Follow docs/development/CODEBASE_RULES.md strictly
3. Update docs when adding modules or functions
4. Test database operations work correctly
5. Ensure imports are clean (no circular dependencies)

### Refactor Agent
**Purpose:** Improve code quality without changing behavior  
**File:** `.agent/roles/refactor.md`

When using:
1. Do not add new features
2. Do not change function signatures
3. Improve naming, clarity, reduce duplication
4. Run same manual tests after refactoring
5. Update only comments and docstrings if needed

### Migration Agent
**Purpose:** Modify database schema safely  
**File:** `.agent/roles/migration.md`

When using:
1. Always update MIGRATIONS.md first
2. Add migration logic to migrations.py
3. Provide rollback instructions
4. Update database.md in docs/
5. Add version check to ensure compatibility

### Analytics Agent
**Purpose:** Add analytics and queries  
**File:** `.agent/roles/analytics.md`

When using:
1. All code goes in analytics/ or new analytics module
2. Read-only operations only
3. No writes to database
4. Update basic_queries.py return types and docstrings
5. Add formatted display methods for CLI

## Command Template for Agents

When invoking an agent, use this structure:

---

**TRAININGLOGS AGENT TASK**

**Role:** [Builder|Refactor|Migration|Analytics]

**Context:**
- You are working on the traininglogs project
- Framework: Python 3.8+, SQLite persistence
- Architecture: See README.md and docs/architecture.md
- Rules: See docs/development/CODEBASE_RULES.md

**Task:**
[Clear description of what to implement]

**Scope:**
- Follow TASKLIST.md phase
- Only modify files listed: [if specified]
- Do not refactor unrelated code

**Testing:**
- Ensure database initializes: `python scripts/init_db.py`
- Test CLI runs: `python -m cli.main`
- Verify no circular imports

**Output:**
- Implement incrementally
- Update docs when adding modules
- Commit message format: `[Task #N] Brief description`

---

## Safety Checks

Before merging agent-produced code:

✅ **No circular imports**
```bash
python -c "import cli.main; print('OK')"
python -c "import persistence.database; print('OK')"
```

✅ **Database operations work**
```bash
python scripts/init_db.py
```

✅ **CLI launches**
```bash
timeout 2 python -m cli.main < /dev/null || true
```

✅ **Rules followed**
- Review against docs/development/CODEBASE_RULES.md
- Check module responsibilities
- Verify validation placement

## Multi-Agent Workflows

### Build New Feature (3-agent)

1. **Builder Agent:** Implement core logic
   - Create new module in appropriate layer
   - Add validation rules to validators.py
   - Implement repository methods if database change

2. **Migration Agent:** Add database changes (if needed)
   - Update docs/development/MIGRATIONS.md
   - Add version logic to migrations.py
   - Test init_db.py

3. **Builder Agent:** Wire to CLI
   - Add prompts to cli/prompts.py
   - Update cli/main.py with feature workflow
   - Add summary/display functions

### Refactor Module (2-agent)

1. **Refactor Agent:** Improve module
   - Keep same signatures
   - Reduce duplication
   - Improve naming

2. **Builder Agent:** Verify and document
   - Run manual tests
   - Update docs if structure changed
   - Commit with summary

## Feedback Loop

After agent execution:

1. **Review** — Read generated code
2. **Test** — Run safety checks
3. **Adjust** — Provide specific feedback
4. **Re-run** — Agent refines based on feedback

Example feedback:
```
The imports in session_manager.py cause a circular dependency.
Move the repository import into the method that uses it:
  def persist_session(self):
      from persistence import TrainingSessionRepository
      # ... rest of code
```

## When an Agent Should Stop

Agent should NOT proceed if:
- ❌ Circular imports detected
- ❌ Database schema breaks existing data format
- ❌ Business logic mixed into CLI
- ❌ Validation placed outside core/validators.py
- ❌ Hardcoded paths used (not in config/settings.py)

In these cases, agent should raise clear error and stop.

## Revision Control

Each agent task should result in:
- One focused commit (or rebase into one)
- Clear commit message
- Updated TASKLIST.md to mark completed

Example:
```bash
git add -A
git commit -m "Implement HistoryService (Phase 3, Task #9)

- Add history_service.py with 6 query methods
- Integrate with repository layer
- Add to history/__init__.py
- Test: exercise history queries work correctly

Follows docs/development/CODEBASE_RULES.md and .agent/PROTOCOL.md"
```

## Future: LLM Orchestration

This protocol is designed to scale to:
- **Parallel agents** — Multiple agents on different features
- **Orchestrator agent** — Routes tasks between specialists
- **Self-healing** — Agents detect and fix common issues
- **Continuous deployment** — Auto-test and deploy on passes

For now, manual human-in-the-loop is the gating point.

````
