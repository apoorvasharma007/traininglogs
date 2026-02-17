# Phase 6: Integration & Testing

Interactive testing phase. Build features needed for end-to-end CLI workflow.

## Phase 6 Overview

**Goal:** Make the CLI fully functional from session logging → persistence → querying.

**Key changes:**
- Integrate HistoryService into exercise builder (show previous exercise data)
- Add analytics CLI subcommand (view training data)
- Error handling and edge cases
- Full end-to-end test

**Timeline:** 1-2 weeks with human-in-the-loop builder agent

**Testing approach:** Manual interactive testing after each task

---

## Task 6.1: Integrate HistoryService into ExerciseBuilder

**Status:** 🚀 READY FOR BUILDER AGENT

**What:** When user logs a new exercise, show previous occurrence (weight, reps, RPE) for reference.

**Example:**
```
Exercise #1 name: Barbell Bench Press

📚 Last occurrence of this exercise:
   Last working set: 80kg × 5 + 0p @ RPE 8
   (from 2025-02-10)
   
📝 Building warmup sets for: Barbell Bench Press
  Warmup Set #1
    Weight (kg): 20   ← User compares to previous
```

### Scope

**Modify:**
- `core/exercise_builder.py` — Add history lookup before building exercise
- `cli/main.py` — Integrate HistoryService into workflow

**Create:**
- None (HistoryService already exists)

**Test:**
```bash
# 1. Initialize DB
python scripts/init_db.py

# 2. Create first session (manual)
python -m cli.main
# Log 1 exercise: "Barbell Bench Press" with 1 working set

# 3. Create second session
python -m cli.main
# When prompted for "Barbell Bench Press", should show previous data
```

**Expected Output:**
```
Exercise #1 name: Barbell Bench Press

📚 Last occurrence of this exercise:
   Last working set: 80kg × 5 + 0p @ RPE 8

📝 Building warmup sets for: Barbell Bench Press
...
```

### Implementation Notes

1. **HistoryService initialization**
   - In `cli/main.py`, create: `history_service = HistoryService(repository)`
   - Pass to `exercise_builder` or call before building

2. **Two approaches:**

   **Approach A (Simpler):** Call history in main.py before building
   ```python
   exercise_name = prompts.prompt_exercise_name(exercise_count)
   previous = history_service.get_last_exercise(exercise_name)
   exercise = exercise_builder.build_exercise(exercise_name, previous)
   ```

   **Approach B (Cleaner):** Inject history_service into builder
   ```python
   builder = ExerciseBuilder(history_service=history_service)
   exercise = builder.build_exercise(exercise_name)
   # Builder calls history internally
   ```

   **Recommendation:** Use Approach A (minimal changes)

3. **Handle missing history gracefully**
   - If no previous exercise, skip the display
   - Don't error, just continue
   - Pattern: `if previous: show_previous_exercise(previous)`

4. **Display format**
   - See `_show_last_exercise()` already in ExerciseBuilder
   - May need to enhance with date info
   - Keep to 1-2 lines for CLI clarity

### Definition of Done

- ✅ User sees previous exercise data when available
- ✅ No error if exercise is new (not found)
- ✅ Display shows: weight, reps, RPE from last occurrence
- ✅ Works across multiple sessions
- ✅ No circular imports introduced
- ✅ Docstrings updated
- ✅ Manual end-to-end test passes

**Responsible Party:** Builder Agent  
**Reviewer:** Human (you)

---

## Task 6.2: Add Analytics Subcommand

**Status:** ⏳ QUEUED

**What:** New CLI command to view training data without logging a session.

**Example:**
```bash
# View last 5 sessions
python -m cli.analytics --last-sessions 5

# View exercise history
python -m cli.analytics --exercise "Barbell Bench Press" --limit 5

# View weekly volume
python -m cli.analytics --weekly-volume --phase "phase 2" --week 5
```

### Scope

**Create:**
- `cli/analytics.py` — New analytics command handler

**Modify:**
- `cli/main.py` — Add subcommand routing (optional, or standalone)

**Or create:**
- `scripts/analytics.py` — Standalone analytics script (simpler path)

### Implementation Options

**Option 1: Subcommand in main.py (cleaner)**
```python
# In cli/main.py
if len(sys.argv) > 1 and sys.argv[1] == "analytics":
    from cli.analytics import run_analytics
    run_analytics(sys.argv[2:])
elif len(sys.argv) > 1 and sys.argv[1] == "log":
    # existing session logging code
else:
    print("Usage: python -m cli.main [log|analytics]")
```

**Option 2: Standalone script (faster)**
```bash
python scripts/analytics.py --last-sessions 5
```

**Recommendation:** Option 2 (simpler for Phase 6, integrate later)

### Commands to Implement

```
--last-sessions N
  Show last N training sessions
  
--exercise NAME [--limit N]
  Show exercise history (weight, reps, RPE progression)
  Limit to N occurrences (default 5)
  
--weekly-volume --phase PHASE --week WEEK
  Show total volume by exercise for phase+week
  
--help
  Show usage
```

### Definition of Done

- ✅ `scripts/analytics.py` works standalone
- ✅ Arg parsing handles all commands
- ✅ Output is readable and formatted
- ✅ Error handling for missing data
- ✅ Works with populated database
- ✅ Docstrings on all commands

**Responsible Party:** Builder Agent  
**Reviewer:** Human (you)

---

## Task 6.3: Error Handling & Edge Cases

**Status:** ⏳ QUEUED

**What:** Improve robustness for real-world usage.

### Edge Cases to Handle

1. **Empty Database**
   ```
   First run, no exercises logged yet
   → Should not crash
   → Show friendly message
   ```

2. **Missing Phase/Week**
   ```
   User presses Enter without entering phase
   → Prompt again
   → Or default to "phase 2" / week 1
   ```

3. **Keyboard Interrupt (Ctrl+C)**
   ```
   User cancels mid-session
   → Gracefully abandon session
   → Show "Cancelled" message
   → Exit cleanly
   ```

4. **Invalid Set Data**
   ```
   User enters "abc" for reps
   → Show error
   → Prompt again (already done in ExerciseBuilder)
   → Verify works for all inputs
   ```

5. **Database Locked**
   ```
   Multiple instances of CLI
   → Show clear error
   → Suggest: "Is another session running?"
   ```

### Scope

**Modify:**
- `cli/main.py` — Add edge case handling
- `cli/prompts.py` — Add error recovery
- `core/exercise_builder.py` — Validate input loops

### Testing Checklist

- [ ] First run with empty DB
- [ ] Cancel session (Ctrl+C) at different points
- [ ] Invalid numeric input (weight, reps, RPE)
- [ ] Empty string input
- [ ] Very large numbers (999999 reps)
- [ ] Negative numbers (caught by validator)
- [ ] Special characters in exercise name
- [ ] Run two CLI instances simultaneously (should fail gracefully)

### Definition of Done

- ✅ No unhandled exceptions
- ✅ Friendly error messages
- ✅ User can recover from mistakes
- ✅ All edge cases tested manually
- ✅ Exit codes correct (0=success, 1=error)

**Responsible Party:** Builder Agent (with manual testing by human)  
**Reviewer:** Human (you)

---

## Task 6.4: End-to-End Testing

**Status:** ⏳ QUEUED

**What:** Manual full workflow test.

### Test Sequence

**Setup:**
```bash
rm -f traininglogs.db  # Fresh start
python scripts/init_db.py
```

**Test 1: Log First Session**
```bash
python -m cli.main
1. Enter phase: phase 2
2. Enter week: 1
3. Enter focus: upper-strength
4. Add exercise: Barbell Bench Press
   - Warmup: 20kg × 5, 40kg × 3
   - Working: 80kg × 5 RPE 8, 82.5kg × 5+1p RPE 10
5. Add exercise: Incline Dumbbell Press
   - Warmup: 25kg × 8
   - Working: 40kg × 8 RPE 8
6. Finish session
7. Review summary
8. Save
```

**Expected:** Session saved, no errors

**Test 2: View Analytics**
```bash
python scripts/analytics.py --last-sessions 1
# Should show 1 session with 2 exercises
```

**Test 3: Log Second Session (Test History)**
```bash
python -m cli.main
1. Same as Test 1
2. When adding "Barbell Bench Press"
   → Should show previous data: 80kg × 5 + 0p @ RPE 8
3. Continue as before
4. Save
```

**Expected:** History displayed, session saved

**Test 4: View Exercise History**
```bash
python scripts/analytics.py --exercise "Barbell Bench Press" --limit 2
# Should show 2 occurrences, progression visible
```

**Test 5: View Weekly Volume**
```bash
python scripts/analytics.py --weekly-volume --phase "phase 2" --week 1
# Should show total volume for phase 2 week 1
```

**Expected:** All sessions/exercises visible, calculations correct

### Pass Criteria

- [ ] No crashes or unhandled exceptions
- [ ] All sessions save correctly
- [ ] Database has correct data (can inspect with sqlite3)
- [ ] History displays when available
- [ ] Analytics show correct data
- [ ] Can run complete workflow 2x without issues
- [ ] Exit codes correct
- [ ] User prompts are clear

### Definition of Done

- ✅ Full end-to-end workflow tested manually
- ✅ All features working together
- ✅ No breaking interactions
- ✅ Documentation matches reality

**Responsible Party:** Human (you)

---

## Phase 6 Timeline

**Week 1:**
- Mon-Tue: Task 6.1 (Builder Agent) → Human Review
- Wed-Thu: Task 6.2 (Builder Agent) → Human Review
- Fri: Task 6.3 (Builder Agent) + Human Testing

**Week 2:**
- Mon-Tue: Task 6.4 (Manual End-to-End Testing)
- Wed: Fix any bugs found
- Thu-Fri: Polish and deploy

**Total Effort:**
- Builder Agent: ~4 hours (distributed across tasks)
- Human Review: ~2 hours (focused review)
- Manual Testing: ~3 hours (thorough testing)

---

## How to Use This Plan

### For Builder Agent

```
PHASE 6 BUILDER AGENT TASK

Task: 6.1 - Integrate HistoryService into ExerciseBuilder

Spec: See /PHASE6.md Task 6.1

Constraints:
- Only modify cli/main.py and core/exercise_builder.py
- Don't refactor unrelated code
- Follow docs/development/CODEBASE_RULES.md and .agent/PROTOCOL.md

Testing:
- Run: python scripts/init_db.py
- Log 1 session, then 2nd session
- Verify history shows on 2nd session

Definition of Done: [list above]
```

### For Human Reviewer

```
When agent completes 6.1:

1. Read generated code
2. Check against "Definition of Done"
3. Run test sequence:
   python scripts/init_db.py
   python -m cli.main
   [log session 1]
   python -m cli.main
   [log session 2, verify history shows]
4. Approve or request changes
5. Merge to traininglogs-agent branch
6. Update TASKLIST.md
```

---

## Success Metrics

After Phase 6 complete:

| Metric | Target | Status |
|--------|--------|--------|
| CLI fully functional | Yes | ⏳ |
| History integration | Working | ⏳ |
| Analytics available | 3 commands | ⏳ |
| Error handling | All edge cases | ⏳ |
| Manual test passing | 5/5 | ⏳ |
| Code review approved | 4/4 tasks | ⏳ |
| Documentation updated | TASKLIST.md | ⏳ |

---

## Next Steps After Phase 6

- **Phase 7:** iOS/Mobile execution strategy (documentation only)
- **Phase 8:** Advanced features (LLM parsing, voice, REST API)
- **Phase 9:** Autonomous loop scaling (multi-agent orchestration)

---

*Created: 2025-02-16 | Phase 6 Ready for Agent-Assisted Development*
