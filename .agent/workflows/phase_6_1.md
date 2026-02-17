````markdown
# Task 6.1: Integrate HistoryService into ExerciseBuilder

**Builder Agent Assignment**

---

## Overview

When a user logs an exercise, show them the **previous occurrence** (weight, reps, RPE) for reference.

**Current behavior:**
```
Exercise #1 name: Barbell Bench Press

📝 Building warmup sets for: Barbell Bench Press
  Warmup Set #1
    Weight (kg): 20
```

**Target behavior:**
```
Exercise #1 name: Barbell Bench Press

📚 Last occurrence of this exercise:
   Last working set: 80kg × 5 + 0p @ RPE 8

📝 Building warmup sets for: Barbell Bench Press
  Warmup Set #1
    Weight (kg): 20
```

---

## Scope

### Files to Modify

1. **`cli/main.py`**
   - Import HistoryService
   - Create history_service instance after repository
   - Pass previous exercise data to exercise_builder

2. **`core/exercise_builder.py`** (OPTIONAL)
   - May not need changes if calling history in main.py
   - Only if refactoring to inject history_service

### Files NOT to Touch

- ❌ `data_class_model/` (existing datamodel)
- ❌ `persistence/` (database layer)
- ❌ `history/` (history service already completed)
- ❌ `config/`, `analytics/`, `docs/`

---

## Implementation Plan

### Step 1: Read Existing Code

```python
# In history/history_service.py
def get_last_exercise(self, exercise_name: str) -> Optional[Dict[str, Any]]:
    """Get the most recent occurrence of a specific exercise."""
    # Already implemented!
```

### Step 2: Modify cli/main.py

**Location:** In the exercise loop (after `prompt_exercise_name()`)

```python
# CURRENT CODE
exercise_name = prompts.prompt_exercise_name(exercise_count)

exercise = exercise_builder.build_exercise(exercise_name)
session_manager.add_exercise(
    name=exercise["name"],
    warmup_sets=exercise.get("warmup_sets"),
    working_sets=exercise.get("working_sets")
)

# DO THIS INSTEAD
from history import HistoryService  # Add import at top

# ... later in main(), after creating repository:
history_service = HistoryService(repository)

# ... in exercise loop:
exercise_name = prompts.prompt_exercise_name(exercise_count)

# Get previous exercise data
previous_exercise = history_service.get_last_exercise(exercise_name)

# Pass to builder
exercise = exercise_builder.build_exercise(exercise_name, previous_exercise)

session_manager.add_exercise(
    name=exercise["name"],
    warmup_sets=exercise.get("warmup_sets"),
    working_sets=exercise.get("working_sets")
)
```

### Step 3: Verify ExerciseBuilder Handles It

Check if `exercise_builder.build_exercise()` already supports `last_exercise_data`:

```python
# In core/exercise_builder.py
def build_exercise(
    self,
    exercise_name: str,
    last_exercise_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Interactively build an exercise with sets.
    
    Args:
        exercise_name: Name of the exercise
        last_exercise_data: Optional previous exercise data for reference
    """
```

✅ **Already implemented!** The second parameter is optional.

### Step 4: Test

```bash
# 1. Initialize clean database
rm -f traininglogs.db
python scripts/init_db.py

# 2. Log first session
python -m cli.main

# Inputs:
# Phase: phase 2
# Week: 1
# Focus: upper-strength
# Deload: n
# Exercise 1: Barbell Bench Press
#   Warmup 1: 20kg x 5
#   Working 1: 80kg x 5, RPE 8, quality: good
# Finish: f
# Save: y

# 3. Log second session
python -m cli.main

# Same inputs as before...
# When prompted for exercise name, should see:
#
# 📚 Last occurrence of this exercise:
#    Last working set: 80kg × 5 + 0p @ RPE 8

# This proves history is working!
```

---

## Code Checklist

- [ ] Import HistoryService at top of cli/main.py
- [ ] Create `history_service = HistoryService(repository)` after repository init
- [ ] Pass `previous_exercise` to `exercise_builder.build_exercise()`
- [ ] ExerciseBuilder calls `_show_last_exercise()` if data provided
- [ ] No circular imports (`python -c "import cli.main"` works)
- [ ] Docstrings accurate
- [ ] Error handling for None/missing exercise

---

## Expected Modifications

**Minimal changes:**
- Add 1 import line
- Add 1 initialization line
- Modify 1 function call (add parameter)

**Total new code:** ~5 lines

---

## Definition of Done

✅ **Code:**
- [ ] Files modified as specified
- [ ] No syntax errors
- [ ] Imports are clean (no circular)
- [ ] Follows docs/development/CODEBASE_RULES.md

✅ **Behavior:**
- [ ] History displays when available
- [ ] No errors if exercise is new
- [ ] History shows correct data (weight, reps, RPE)
- [ ] Works across multiple sessions

✅ **Testing:**
- [ ] Run: `python .agent/scripts/verify_changes.py` → PASS
- [ ] Manual test: Log session 1 with 1 exercise
- [ ] Manual test: Log session 2 with same exercise
- [ ] Verify history displays on session 2

✅ **Documentation:**
- [ ] Docstring on any modified functions
- [ ] No README changes needed for this task

---

## How to Execute

1. **Plan (2 min):**
   - Read this spec
   - Read cli/main.py and exercise_builder.py
   - Plan your 3-5 changes

2. **Implement (5 min):**
   - Add import
   - Add history_service init
   - Modify exercise build call
   - Add docstring if needed

3. **Test (5 min):**
   - `python scripts/init_db.py`
   - `python -m cli.main` (session 1)
   - `python -m cli.main` (session 2, verify history)
   - `python .agent/scripts/verify_changes.py`

4. **Output (2 min):**
   - Show modified cli/main.py
   - Show test results
   - List all changes made

**Total Time:** ~15 minutes

---

## Red Flags (Stop Here)

If you encounter:

- ❌ Circular import error → Move HistoryService import into exercise loop
- ❌ AttributeError on history_service → Verify HistoryService imported correctly
- ❌ Exercise builder crashes → Check exercise data format matches expected
- ❌ History always None → Check repository has data (run test workflow)

**In any error case:** Provide specific error message with traceback.

---

## Success Example

When this task is complete, running the test workflow should output:

```
🏋️  traininglogs CLI v1
==================================================

🏋️  Starting new training session
==================================================

Phase: phase 2
Week: 1
Workout focus: upper-strength
Is this a deload week? (y/n): n

ℹ️  Session started: abc12345...

Exercise #1 name: Barbell Bench Press

(no history yet, first exercise)

📝 Building warmup sets for: Barbell Bench Press
...
(save session 1)

---
(Run CLI again)
---

Exercise #1 name: Barbell Bench Press

📚 Last occurrence of this exercise:          ← THIS IS THE SIGN OF SUCCESS
   Last working set: 80kg × 5 + 0p @ RPE 8

📝 Building warmup sets for: Barbell Bench Press
```

---

**Ready to execute?** Signal when complete with:
- Modified files
- Test output
- Any issues encountered

````
