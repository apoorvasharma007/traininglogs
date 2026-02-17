# Option A: Phase 6 Quick Start

Follow this guide to execute Phase 6 with human-in-the-loop builder agent.

---

## Your Workflow (Simplified)

```
1. TASK CREATION (You)
   Read task spec in TASKS/X.md
   
2. BUILD (Builder Agent) 
   Agent modifies code + tests
   
3. REVIEW (You)
   Run safety check
   Run manual test
   Check code quality
   
4. APPROVE (You)
   Merge to traininglogs-agent
   Mark task complete
   
5. REPEAT
   Next task → Loop to step 2
```

---

## Phase 6 Task List

| Task | Status | Spec | Est. Time |
|------|--------|------|-----------|
| 6.1 | 🚀 READY | [.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md) | 15 min |
| 6.2 | ⏳ NEXT | .agent/workflows/phase_6_2.md | 20 min |
| 6.3 | ⏳ QUEUE | .agent/workflows/phase_6_3.md | 20 min |
| 6.4 | ⏳ QUEUE | Manual testing | 30 min |

**Total Phase 6 time:** ~3-4 hours (mostly testing)

---

## Right Now: Execute Task 6.1

### For Builder Agent (If you have one)

```
Read this spec:
→ /Users/apoorvasharma/local/traininglogs/.agent/workflows/phase_6_1.md

Then:
1. Implement the changes
2. Run: python scripts/init_db.py
3. Test manually (2 sessions)
4. Verify: python scripts/verify_agent_changes.py
5. Show me:
   - Modified files
   - Test output
   - Any issues

Expected time: ~15-20 minutes
```

### For You (Manual Option)

If implementing yourself instead of using an agent:

**Step 1: Understand the Feature**

```python
# Goal: Show previous exercise data when logging new exercise

# Example:
Exercise #1 name: Barbell Bench Press

📚 Last occurrence:                    ← Show this!
   Last working set: 80kg × 5 @ RPE 8

📝 Building warmup sets...
```

**Step 2: Needed Changes**

In `cli/main.py`:
1. Import: `from history import HistoryService`
2. Initialize: `history_service = HistoryService(repository)`
3. Pass to builder: `previous = history_service.get_last_exercise(name)`
4. Pass to build_exercise: `exercise_builder.build_exercise(name, previous)`

**Step 3: Test**

```bash
# Fresh start
rm -f traininglogs.db
python scripts/init_db.py

# First session
python3 -m cli.main
# Inputs: phase 2, week 1, focus upper, deload n
# Exercise: Barbell Bench Press
# Warmup: 20kg x 5
# Working: 80kg x 5, RPE 8
# Finish (f), Save (y)

# Second session (history should show)
python3 -m cli.main
# Same inputs, same exercise
# Should see: "📚 Last occurrence: 80kg x 5 @ RPE 8"

# Verify
python scripts/verify_agent_changes.py
```

**Step 4: If Stuck**

See HUMAN_REVIEW_GUIDE.md section "Common Agent Issues"

---

## After Task 6.1 Complete

1. **Update TASKLIST.md**
   ```markdown
   # Change this:
   - ⏳ Task 6.1: Integrate HistoryService
   
   # To this:
   - ✅ Task 6.1: Integrate HistoryService
   ```

2. **Test Analytics (Preview of 6.2)**
   ```bash
   # To confirm database is working:
   sqlite3 traininglogs.db "SELECT COUNT(*) FROM training_sessions"
   # Should show: 2
   ```

3. **Start Task 6.2**
   ```bash
   # Read spec
   cat .agent/workflows/phase_6_2.md
   
   # (instructions TBD - will create when Task 6.1 complete)
   ```

---

## Key Files You Need

| File | Purpose |
|------|---------|
| [PHASE6.md](PHASE6.md) | Full Phase 6 spec (4 tasks) |
| [.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md) | Task 6.1 detailed spec |
| [HUMAN_REVIEW_GUIDE.md](HUMAN_REVIEW_GUIDE.md) | How to review agent code |
| [.agent/PROTOCOL.md](.agent/PROTOCOL.md) | Agent rules + safety |
| [scripts/verify_agent_changes.py](scripts/verify_agent_changes.py) | Safety verification gate |

---

## Safety Checks (Always Run These)

```bash
# 1. Verify no import errors
python3 -c "import cli.main; print('✓ CLI imports OK')"

# 2. Database works
python scripts/init_db.py

# 3. Safety gate passes
python scripts/verify_agent_changes.py

# 4. Manual test passes (see HUMAN_REVIEW_GUIDE.md)
```

---

## What's Working Now

✅ **Completed (Phases 1-5):**
- Database initialization
- Session management (in-memory)
- Exercise builder with prompts
- Validators
- CLI entry point
- History service (read-only)
- Analytics queries
- Full documentation
- Agent governance files

⏳ **In Progress (Phase 6):**
- History integration with CLI
- Analytics CLI commands
- Error handling
- Full end-to-end testing

---

## Commitment

**Option A approach requires:**
- ✅ Read task spec (5 min)
- ✅ Wait for agent output (async)
- ✅ Review code (10 min)
- ✅ Run tests manually (5 min)
- ✅ Approve or request changes (5 min)

**Time per task:** 15-30 minutes (mostly testing)

**Total Phase 6:** 3-4 hours over 1-2 weeks

**Time savings vs manual coding:** ~50% (agent does implementation, you do QA)

---

## Next Phase

After Phase 6 complete:

**Phase 7:** iOS/Mobile execution strategy (documentation only, ~15 min)

**Phase 8+:** Advanced features (future planning)

---

## Questions?

See:
- Architecture: [docs/architecture.md](docs/architecture.md)
- Database: [docs/database.md](docs/database.md)
- Session Flow: [docs/session_flow.md](docs/session_flow.md)
- Agent Protocol: [.agent/PROTOCOL.md](.agent/PROTOCOL.md)
- Code Rules: [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)

---

## Ready?

**Next action:**

```bash
# Option A: Use AI Agent
# → Provide agent with: .agent/workflows/phase_6_1.md
# → Wait for code output
# → Follow HUMAN_REVIEW_GUIDE.md to approve

# Option B: Implement Yourself
cd /Users/apoorvasharma/local/traininglogs
# → Read .agent/workflows/phase_6_1.md
# → Follow implementation steps
# → Test with verify script
# → Mark complete in TASKLIST.md
```

Good luck! 🚀
