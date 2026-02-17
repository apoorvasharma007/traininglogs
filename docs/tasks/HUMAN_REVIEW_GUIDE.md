# Human Review Guide for Agent-Produced Code

How to review and approve builder agent work for Phase 6.

---

## Review Philosophy

**Your role:** Quality gate before code merges.

**Not your role:** Implement the code (agent does this).

**Goal:** Catch issues agent might miss (logic errors, edge cases, architecture violations).

**Timeline:** 10-15 min per task review.

---

## Pre-Review Checklist

Before reviewing agent code:

- [ ] Read the task spec (PHASE6.md or TASKS/*.md)
- [ ] Read the agent output (code snippets + explanation)
- [ ] Understand what changed
- [ ] Know the success criteria

---

## Review Workflow

### Step 1: Quick Code Scan (2 min)

**Look for obvious issues:**

✅ **GOOD SIGNS:**
- [ ] Functions have docstrings
- [ ] Code is readable (clear variable names)
- [ ] Imports at top of file
- [ ] No `print()` statements mixed with logic
- [ ] Error handling present (`if not x: raise`)

❌ **RED FLAGS:**
- [ ] New imports not listed at top
- [ ] Circular imports (A imports B, B imports A)
- [ ] Business logic in CLI layer
- [ ] Validation outside `core/validators.py`
- [ ] Hardcoded paths or values
- [ ] Comments like "TODO" or "HACK"

**Decision:** If red flags, request changes before testing.

### Step 2: Run Safety Verification (1 min)

```bash
cd /Users/apoorvasharma/local/traininglogs
python scripts/verify_agent_changes.py
```

**Output should be:**
```
1️⃣  Checking imports...
   ✓ CLI
   ✓ Core
   (all ✓)

2️⃣  Checking database...
   ✓ Schema initialization
   ✓ Schema version: 1

3️⃣  Checking code format (black)...
   ✓ Code formatting OK

4️⃣  Checking code lint (ruff)...
   ✓ Code lint OK

✅ VERIFICATION PASSED
```

**If it fails:**
- Note which check failed
- This usually means agent made a structural error
- Request changes and retry

### Step 3: Test the Feature (5-10 min)

Run the manual test workflow specific to the task.

**Example: Task 6.1 (History Integration)**

```bash
# Start fresh
rm -f traininglogs.db
python scripts/init_db.py

# Test 1: First session (no history)
python -m cli.main
# → Phase 2, Week 1, Focus upper, deload n
# → Exercise: Barbell Bench Press
# → Warmup: 20kg × 5
# → Working: 80kg × 5 RPE 8
# → Finish (f) and Save (y)

# Result: Check visually that:
# - No errors printed
# - ✓ Session saved!
# - Database now has 1 session

# Test 2: Second session (history should show)
python -m cli.main
# → Same as Test 1 (Phase 2, Week 1, etc.)
# → Exercise: Barbell Bench Press
# ✓ CRITICAL: Should show:
#    📚 Last occurrence of this exercise:
#       Last working set: 80kg × 5 + 0p @ RPE 8
# → If you see this, test PASSES
# → If you don't, test FAILS (request changes)
# → Continue logging same exercise
# → Then Finish (f) and Save (y)

# Result check in database
sqlite3 traininglogs.db "SELECT COUNT(*) FROM training_sessions"
# Should output: 2
```

**For other tasks**, consult PHASE6.md for specific test sequence.

### Step 4: Edge Case Testing (Optional but Good)

Test things that could go wrong:

```bash
# Test: Cancel mid-session
python -m cli.main
# → Press Ctrl+C during exercise build
# Expected: Graceful exit, ⏸️ Interrupted by user.

# Test: Invalid input
python -m cli.main
# → When prompted for weight, enter "abc"
# Expected: ❌ Invalid weight, prompt again

# Test: Empty database
rm -f traininglogs.db
python -m cli.main
# Expected: Runs fine, saves first session
```

### Step 5: Code Review Notes

If you find issues, document them:

**Example feedback:**

```markdown
# Review Notes for Task 6.1

## Issues Found

### Issue 1: Missing docstring
In cli/main.py, line 42:
```python
history_service = HistoryService(repository)
```
Add docstring explaining what this does.

**Fix:** Add 1-line comment above line

### Issue 2: Untested edge case
What happens if exercise_name is empty string?
Test this case.

**Fix:** Run test with empty input, verify error message

## No show-stoppers, but...
- Consider adding `try/except` on history_service.get_last_exercise()
- If exercise not found, current code returns None gracefully ✓
- OK to approve

## Approval: 👍 APPROVED with minor notes
```

### Step 6: Approve or Request Changes

**APPROVE:**
- All safety checks pass
- Manual test passes
- No red flags
- Code follows standards

```bash
# Merge to traininglogs-agent
git add -A
git commit -m "Task 6.1: Integrate HistoryService into CLI

- Import HistoryService in cli/main.py
- Create history_service instance
- Pass previous exercise to exercise_builder
- User now sees last workout data while logging new exercise

Verified: safety checks pass, manual test pass"

git push origin traininglogs-agent
```

**REQUEST CHANGES:**
- Safety checks fail (circular imports, etc.)
- Manual test fails (feature doesn't work)
- Code violates standards
- Agent misunderstood requirements

```markdown
# Review: REQUEST CHANGES

Please fix these issues:

1. **Circular Import in core/exercise_builder.py**
   - Line 12: `from cli import prompts`
   - Fix: Move this import into the method that uses it
   
2. **Missing Docstring**
   - Function `_show_last_exercise()` has no docstring
   - Add: Explain what it displays and why
   
3. **Test Failure**
   - History not showing on 2nd session
   - Debug: print what `history_service.get_last_exercise()` returns
   - Trace: Is it querying database correctly?

Once fixed, re-run tests and re-submit for review.
```

---

## Red Flags Decision Tree

```
Does code pass safety check?
    ├─ NO → Request changes (structural issue)
    └─ YES → Continue

Does manual test pass?
    ├─ NO → Request changes (feature broken)
    └─ YES → Continue

Does code follow docs/development/CODEBASE_RULES.md?
    ├─ NO → Request changes (violation)
    └─ YES → Continue

Does agent explain their changes?
    ├─ NO → Request summary
    └─ YES → Continue

Are there obvious bugs?
    ├─ NO → Approve ✅
    └─ YES → Request fixes

```

---

## Common Agent Issues & Fixes

### Issue: "Circular import detected"

**Symptom:**
```
File "cli/main.py", line 10, in <module>
  from core.session_manager import SessionManager
File "core/session_manager.py", line 5, in <module>
  from cli.prompts import show_info
ImportError: cannot import name 'show_info' from 'cli.prompts'
```

**Fix Request:**
```markdown
## Circular Import in session_manager.py

Move the import into the method that uses it:

BEFORE:
```python
from cli.prompts import show_info

class SessionManager:
    def finish_session(self):
        show_info("...")
```

AFTER:
```python
class SessionManager:
    def finish_session(self):
        from cli.prompts import show_info
        show_info("...")
```

This breaks the circular dependency.
```

### Issue: "Feature doesn't work"

**Symptom:**
```
Test: Log 2 sessions, history should show on 2nd
Result: No history displayed
```

**Fix Request:**
```markdown
## History Not Displaying

Your code:
```python
previous = history_service.get_last_exercise(exercise_name)
exercise_builder.build_exercise(exercise_name, previous)
```

Debug steps:
1. Add print to see what `previous` contains:
   ```python
   print(f"DEBUG: previous = {previous}")
   exercise_builder.build_exercise(...)
   ```

2. Run test again and paste the debug output

3. If `previous = None`:
   - Is repository.get_session() working?
   - Does DB have data? Check: sqlite3 traininglogs.db "SELECT COUNT(*) FROM training_sessions"
   - What does get_last_occurrence_of_exercise() return for that exercise name?

4. If `previous = {...}` (has data):
   - Why isn't exercise_builder displaying it?
   - Check if _show_last_exercise() is being called
   - Add print there too to see if it's reached
```

### Issue: "Validation not working"

**Symptom:**
```
Test: Enter negative reps (-5)
Expected: Error message
Actual: No error, negative reps accepted
```

**Fix Request:**
```markdown
## Validation Not Applied

The validators.validate_reps() exists, but you're not calling it in exercise_builder.py.

Add validation call:
```python
# In ExerciseBuilder._build_single_set()
while True:
    try:
        reps = int(input("Full reps: ").strip())
        self.validators.validate_reps(reps)  # ← ADD THIS LINE
        return reps
    except ValidationError as e:
        print(f"Invalid: {e}")
```
```

---

## Approval Checklist

Before clicking "Approve":

```
BEFORE APPROVING:

✅ Code Review
  [ ] Code is readable
  [ ] No obvious bugs
  [ ] Follows naming conventions
  [ ] Docstrings present
  [ ] Error handling adequate

✅ Safety Checks
  [ ] verify_agent_changes.py passes
  [ ] No circular imports
  [ ] No hardcoded paths
  [ ] Validation in correct module

✅ Feature Test
  [ ] Works as specified
  [ ] Edge cases handled
  [ ] No crashes
  [ ] Output is clear

✅ Standards
  [ ] Follows docs/development/CODEBASE_RULES.md
  [ ] Uses correct layer (CLI/Core/Persistence)
  [ ] Type hints present
  [ ] No dead code

✅ Documentation
  [ ] Agent explained changes
  [ ] Commit message clear
  [ ] README/TASKLIST.md ready to update
  
DECISION:
  [ ] APPROVE - Ready to merge
  [ ] REQUEST CHANGES - See feedback above
```

---

## Time Budget

**Per task review:**
- Code scan: 2 min
- Safety verify: 1 min
- Manual test: 8 min
- Decision: 2 min
- **Total: ~15 minutes**

---

## Escalation

**If you can't resolve an issue:**

1. Document what you tried
2. Show agent the problem with screenshot/output
3. Ask agent to debug
4. If still stuck: Fall back to human implementation

**This is OK!** Not every agent task will succeed. That's why humans gate.

---

## After Approval

Once approved:

```bash
# 1. Update TASKLIST.md
# Change: 
#   ⏳ Task 6.1: ...
# To:
#   ✅ Task 6.1: ...

# 2. Commit to traininglogs-agent
git add -A
git commit -m "Task 6.1: Integrate HistoryService - APPROVED"

# 3. Note completion time
# (helps with future planning)

# 4. Next task
# Start Task 6.2 with same workflow
```

---

## Tips for Effective Reviews

1. **Be specific** — "This is wrong" vs. "Line 15 should return dict not str"
2. **Show examples** — "If exercise is new, None is returned. Current code doesn't handle this:"
3. **Test thoroughly** — Use the manual test scripts, don't skip testing
4. **Be fair** — Agent is trying its best. Appreciate good work, fix bad work
5. **Document everything** — Your review is teaching the agent too

---

Ready to review Task 6.1?

1. ✅ Read .agent/workflows/phase_6_1.md
2. 👀 Wait for agent output
3. 🔒 Run: `python scripts/verify_agent_changes.py`
4. 🧪 Run: Manual test (log 2 sessions, verify history)
5. ✅ or  ❌ Approve or request changes
6. 📝 Update TASKLIST.md
7. 🚀 Next task
