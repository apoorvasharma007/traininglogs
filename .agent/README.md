# Agent Governance Folder

This folder contains all agent-related documents and tools.

## Structure

### `PROTOCOL.md`
The main agent governance document. All agents read this first.
- Agent role definitions
- Constraints and workflows
- Multi-agent patterns
- Safety checks
- Feedback loops

### `roles/`
Individual role specifications for each agent type:
- **`builder.md`** — Implement features from TASKLIST.md
- **`refactor.md`** — Improve code without changing behavior
- **`migration.md`** — Evolve database schema safely
- **`analytics.md`** — Add analytical queries (read-only)

### `workflows/`
Task specifications for each Phase 6 task:
- **`phase_6_1.md`** — Integrate HistoryService
- `phase_6_2.md` — Analytics CLI subcommand (TBD)
- `phase_6_3.md` — Error handling (TBD)
- `phase_6_4.md` — E2E testing (TBD)

### `scripts/`
Agent tools:
- **`verify_changes.py`** — Safety verification gate (imports, DB, format, lint)

## When to Use

### If you're an agent:
1. Read `.agent/PROTOCOL.md` (main rules)
2. Read your role file in `.agent/roles/` (specific constraints)
3. Read your task in `.agent/workflows/` (what to implement)
4. Implement, test locally, run safety verification
5. Return code with test results

### If you're a human reviewing agent code:
1. Read `.agent/PROTOCOL.md` to understand the workflow
2. Run `python .agent/scripts/verify_changes.py` (automated checks)
3. Manual test the feature (test procedure in task spec)
4. Review code against role constraints
5. Approve or request changes

## Key Documents

- **For architecture:** See [../docs/](../docs/)
- **For code standards:** See [../docs/development/CODEBASE_RULES.md](../docs/development/CODEBASE_RULES.md)
- **For database info:** See [../docs/development/MIGRATIONS.md](../docs/development/MIGRATIONS.md)
- **For overall roadmap:** See [../TASKLIST.md](../TASKLIST.md)

## Scaling

This structure enables:
- ✅ Single agent on single task (current)
- ✅ Multiple agents on different tasks (Phase 7)
- ✅ Orchestrator agent routing (Phase 8)
- ✅ Auto-approval for safe changes (Phase 9)

See [../AUTONOMOUS_CODING_LOOP.md](../AUTONOMOUS_CODING_LOOP.md) for full scaling strategy.
