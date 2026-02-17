# 🚀 START HERE: Getting Ready to Build

**Goal:** Get you up to speed and ready to implement Task 6.1 in 1 hour.

---

## ✅ Step 1: Understand Current Status (15 minutes)

Read **[DEV_STATUS.md](DEV_STATUS.md)** — Complete guide covering:
- Where we are in development (Phase 6, ready to start)
- How work is tracked (TASKLIST.md, specs, etc.)
- How to run the code (`python scripts/init_db.py`, `python -m src.cli.main`)
- Coding standards & commit message format

**Skip if you're in a rush:** Jump to Step 2 below.

---

## ✅ Step 2: Understand What to Build (10 minutes)

Read **[.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md)** — Implementation spec for:
- **What:** Integrate HistoryService into ExerciseBuilder
- **Why:** Show users previous exercise data while logging
- **Files to modify:** `src/cli/main.py` (primary), `src/cli/prompts.py` (optional)
- **How:** Step-by-step code samples and instructions
- **Testing:** How to verify it works

**Time:** 5-10 minutes to read and understand.

---

## ✅ Step 3: Know the Rules (10 minutes)

Read **[docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)** — Coding standards covering:
- Module responsibilities (what lives where)
- What's allowed in each module
- Code style & structure
- Import rules (no circular imports!)

**Focus on:**
- Section "Module Responsibilities" (table showing what code goes where)
- Section "Core Principles" (the 7 key rules)

---

## ✅ Step 4: Review Current Code (15 minutes)

skim **[src/cli/main.py](src/cli/main.py)** to understand:
- How the CLI currently imports modules
- How database and repository are initialized
- Where the exercise loop is
- Current imports from history, core, etc.

**Don't memorize**, just get familiar with the structure.

---

## ✅ Step 5: Test the Setup (10 minutes)

Run these commands to verify everything works:

```bash
# Initialize database
python scripts/init_db.py
# Expected output: "Database initialized at traininglogs.db"

# Test CLI launches (this will start interactive mode, hit Ctrl+C)
python -m src.cli.main
# Should show: "🏋️  traininglogs CLI v1"

# Verify imports work
python -c "from src.cli.main import main; print('✓ Imports OK')"
# Expected output: "✓ Imports OK"

# Run safety verification
python .agent/scripts/verify_changes.py
# Should pass without errors
```

If all commands succeed → You're ready to implement!

If something fails:
- Check Python version: `python --version` (should be 3.8+)
- Check you're in the right directory
- Read error messages carefully

---

## ✅ Step 6: Implement Task 6.1 (35 minutes)

Follow the implementation guide in **[.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md)**:

1. **Modify `src/cli/main.py`:**
   - Import `HistoryService` from history module
   - Create history_service instance after repository
   - Pass previous exercise data to exercise_builder
   
2. **Optional: Update `src/cli/prompts.py`:**
   - Display previous exercise data in prompts
   - Show "Last occurrence: 80kg × 5 @ RPE 8" format

3. **Test as you go:**
   ```bash
   python scripts/init_db.py  # Verify DB still works
   python -m src.cli.main     # Try logging exercise
   ```

---

## ✅ Step 7: Verify & Test (10 minutes)

Before committing:

```bash
# 1. No circular imports
python -c "from src.cli.main import main; print('✓')"

# 2. Database still initializes
python scripts/init_db.py

# 3. CLI launches (Ctrl+C to exit)
timeout 2 python -m src.cli.main < /dev/null || true

# 4. Full safety check
python .agent/scripts/verify_changes.py
```

All passing? → Ready to commit!

---

## ✅ Step 8: Commit Changes (5 minutes)

```bash
# Stage changes
git add -A

# Commit with proper format
git commit -m "[Task 6.1] Integrate HistoryService into ExerciseBuilder"

# Detailed example with more info (optional):
git commit -m "[Task 6.1] Integrate HistoryService into ExerciseBuilder

- Import HistoryService in cli/main.py
- Create history_service instance after repository
- Pass previous_exercise to exercise_builder.build_exercise()
- Display last occurrence in prompts

Tested: Database init + CLI launch verified"
```

---

## 📚 If You Need Help

### "I don't understand something in the task spec"
→ Read [docs/architecture.md](docs/architecture.md) for system design context

### "I don't know where to put code"
→ Check [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md) Module Responsibilities section

### "What does HistoryService do?"
→ Read [src/history/history_service.py](src/history/history_service.py) (already implemented)

### "How do I run the tests?"
→ See Step 5 above; also in [DEV_STATUS.md#how-to-run-the-code](DEV_STATUS.md#-how-to-run-the-code)

### "How do agents work?"
→ [.agent/PROTOCOL.md](.agent/PROTOCOL.md)

### "I made changes and now imports are broken"
→ Run `python .agent/scripts/verify_changes.py` to see what's wrong

---

## ⏱️ Time Breakdown

| Step | Time | Activity |
|------|------|----------|
| 1 | 15 min | Read DEV_STATUS.md to understand project status |
| 2 | 10 min | Read task spec (.agent/workflows/phase_6_1.md) |
| 3 | 10 min | Review coding standards (CODEBASE_RULES.md) |
| 4 | 15 min | Skim current code (src/cli/main.py) |
| 5 | 10 min | Test setup (run 4 verification commands) |
| 6 | 35 min | Implement Task 6.1 |
| 7 | 10 min | Verify & test changes |
| 8 | 5 min | Commit with proper message |
| **TOTAL** | **100 min** | **1 hour 40 minutes** |

**Optional (adds 30 min):** Deep dive into architecture.md + database.md for full context

---

## 🎯 Success Criteria

After completing all 8 steps, you should be able to:

✅ Explain where Phase 6 Task 1 fits in the overall roadmap  
✅ Run the database initialization script  
✅ Run the CLI application  
✅ Understand the current code structure  
✅ Know the coding standards that apply  
✅ Have implemented HistoryService integration  
✅ Have verified all safety checks pass  
✅ Have committed code with proper message format  

---

## 🚀 Next

Once Task 6.1 is complete and committed:

1. Get code reviewed (have someone check it against CODEBASE_RULES.md)
2. Merge to main branch
3. Move to Task 6.2 (Analytics CLI Subcommand)
4. Repeat the cycle

---

## 📍 You Are Here

```
[Start] → [Read Status] → [Read Spec] → [Learn Rules] → [Review Code] 
   → [Test Setup] → [Implement] → [Verify] → [Commit] → [Next Task]
    ↑                                                        ↓
    ←─────────── REPEAT FOR EACH TASK IN TASKLIST ─────────→
```

---

## 📖 Reference Documentation

All important docs linked:

| Need | Document |
|------|----------|
| Complete status overview | [DEV_STATUS.md](DEV_STATUS.md) |
| Quick navigation | [PROCESS_MAP.md](PROCESS_MAP.md) |
| Task specification | [.agent/workflows/phase_6_1.md](.agent/workflows/phase_6_1.md) |
| Coding standards | [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md) |
| Agent governance | [.agent/PROTOCOL.md](.agent/PROTOCOL.md) |
| Contribution guide | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Complete roadmap | [docs/tasks/TASKLIST.md](docs/tasks/TASKLIST.md) |
| Phase 6 details | [docs/tasks/PHASE6.md](docs/tasks/PHASE6.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Database | [docs/database.md](docs/database.md) |

---

**Ready?** Start with Step 1 above, or jump straight to Step 6 if you already understand the project.

**Questions?** Check the "If You Need Help" section, or read the reference docs above.
