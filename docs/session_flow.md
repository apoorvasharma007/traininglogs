# Session Flow

Step-by-step user workflow for logging a training session.

## High-Level Flow

```
Start CLI
    ↓
Prompt for MetaData
    ↓
Create Session
    ↓
Loop: Add Exercises
    ├─ Prompt Exercise Name
    ├─ Show Previous Exercise (optional)
    ├─ Build Warmup Sets
    ├─ Build Working Sets
    └─ Add to Session
    ↓
Show Summary
    ↓
Confirm & Save
    ↓
Persist to Database
    ↓
Exit
```

## Step-by-Step Workflow

### 1. Start Application

```bash
python -m cli.main
```

**Output:**
```
🏋️  traininglogs CLI v1
==================================================
```

**State:**
- Database initialized
- Schema version verified
- Repository and managers created

### 2. Prompt for Session Metadata

**Prompts:**
```
🏋️  Starting new training session
==================================================

Phase (phase 1, phase 2, phase 3): phase 2
Week number: 5
Workout focus (e.g., upper-strength, legs-hypertrophy): upper-strength
Is this a deload week? (y/n): n
```

**Data Collected:**
```python
metadata = {
    "phase": "phase 2",
    "week": 5,
    "focus": "upper-strength",
    "is_deload": False
}
```

**Action:**
```python
session = session_manager.start_session(**metadata)
```

**State:**
- Session object created with UUID
- session.exercises = []
- UI shows: "Session started: abc12345..."

### 3. First Exercise Loop

User is asked: "(a)dd exercise, (f)inish session, (c)ancel? [a/f/c]:"

#### Case: Add Exercise (a)

**Prompt:**
```
Exercise #1 name: Barbell Bench Press
```

**Action:**
```python
exercise_name = "Barbell Bench Press"
```

#### 3a. Show Previous Exercise (optional)

If history exists:
```
📚 Last occurrence of this exercise:
   Last working set: 80kg × 5 + 0p @ RPE 8
```

**Action:**
```python
history_service.get_last_exercise("Barbell Bench Press")
# Returns previous exercise data
```

#### 3b. Build Warmup Sets

**Flow:**
```
📝 Building warmup sets for: Barbell Bench Press

  Warmup Set #1
    Weight (kg): 20
    Full reps: 5
  Add another warmup set? (y/n): y

  Warmup Set #2
    Weight (kg): 40
    Full reps: 3
  Add another warmup set? (y/n): n
```

**Data:**
```python
warmup_sets = [
    {"weight_kg": 20, "full_reps": 5},
    {"weight_kg": 40, "full_reps": 3}
]
```

#### 3c. Build Working Sets

**Flow:**
```
📝 Building working sets for: Barbell Bench Press

  Working Set #1
    Weight (kg): 80
    Full reps: 5
    Partial reps (or press Enter for 0): 
    RPE (1-10, or press Enter to skip): 8
    Rep quality (good/bad/perfect/learning, or skip): good
  Add another working set? (y/n): y

  Working Set #2
    Weight (kg): 82.5
    Full reps: 5
    Partial reps (or press Enter for 0): 1
    RPE (1-10, or press Enter to skip): 10
    Rep quality (good/bad/perfect/learning, or skip): perfect
  Add another working set? (y/n): n
```

**Data:**
```python
working_sets = [
    {
        "weight_kg": 80,
        "full_reps": 5,
        "partial_reps": 0,
        "rpe": 8,
        "rep_quality": "good"
    },
    {
        "weight_kg": 82.5,
        "full_reps": 5,
        "partial_reps": 1,
        "rpe": 10,
        "rep_quality": "perfect"
    }
]
```

#### 3d. Add Exercise to Session

**Action:**
```python
exercise = exercise_builder.build_exercise("Barbell Bench Press")
session_manager.add_exercise(
    name="Barbell Bench Press",
    warmup_sets=warmup_sets,
    working_sets=working_sets
)
```

**Output:**
```
✓ Added exercise: Barbell Bench Press
```

**State:**
- session.exercises[0] now contains the exercise

### 4. Continue Exercise Loop

**Prompt:**
```
(a)dd exercise, (f)inish session, (c)ancel? [a/f/c]: a
```

**Loop back to step 3** for next exercise.

Or:

#### Case: Finish Session (f)

Break out of exercise loop.
```python
break  # Exit while True loop
```

#### Case: Cancel (c)

```
(a)dd exercise, (f)inish session, (c)ancel? [a/f/c]: c
```

**Action:**
```python
session_manager.cancel_session()
```

**Output:**
```
ℹ️  Session cancelled.
```

**Exit:** Return to CLI with exit code 0.

### 5. Show Session Summary

After finishing session:

```
📊 Session Summary
==================================================
Phase: phase 2
Week: 5
Focus: upper-strength
Deload: No
Exercises: 2
  - Barbell Bench Press: 2 working sets
  - Squat: 3 working sets
```

**Action:**
```python
prompts.show_session_summary(session)
```

### 6. Confirm Save

**Prompt:**
```
✓ Save session? (y/n): y
```

#### Case: Save (y)

**Action:**
```python
session_manager.persist_session()
# Internally:
#   1. Validate session
#   2. Save to repository
#   3. Write to database
#   4. Clear in-memory session
```

**Output:**
```
✓ Session saved!
```

**State:**
- Session written to database
- session_manager.current_session = None

#### Case: Don't Save (n)

**Action:**
```python
session_manager.cancel_session()
```

**Output:**
```
ℹ️  Session not saved.
```

### 7. Exit

```
Exit application
→ Close database connection
→ Return exit code 0
```

---

## Error Handling

### Validation Errors

During session finish:
```python
try:
    session_manager.finish_session()
except ValidationError as e:
    # Show error
    prompts.show_error(str(e))
    # User can re-edit before saving (not implemented yet)
```

**Example:**
```
❌ Error: Exercise 'Barbell Bench Press' must have at least 1 working set
Session must have at least 1 exercise
```

### Database Errors

During save:
```python
try:
    session_manager.persist_session()
except Exception as e:
    prompts.show_error(str(e))
    # Session in-memory stays intact, user can retry
```

### Keyboard Interrupt

```python
except KeyboardInterrupt:
    print("\n⏸️  Interrupted by user.")
    # Exit gracefully
```

---

## Alternative Flows

### Quick Log (Future Enhancement)

Skip prompts with shorthand:
```bash
python -m cli.main --quick "bench 80x5"
```

Would parse and log directly (not in v1).

### Edit Previous Session

Re-open and modify an existing session (not in v1):
```bash
python -m cli.main --session-id abc12345
```

### View Session Before Saving

Show detailed form before committing (not in v1):
```
Edit exercises before saving?
[1] Modify Bench Press
[2] Delete Deadlifts
[3] Continue to save
[c] Cancel
```

---

## State Machine

Simplified state diagram:

```
┌─ START
│
├─ IDLE (between sessions)
│   └─ start_session() → SESSION_ACTIVE
│
├─ SESSION_ACTIVE
│   ├─ add_exercise() → (stays)
│   ├─ finish_session() → READY_TO_SAVE
│   └─ cancel_session() → IDLE
│
├─ READY_TO_SAVE
│   ├─ persist_session() → SAVED
│   └─ cancel_session() → IDLE
│
├─ SAVED
│   └─ (wait for next session)
│       → IDLE
│
└─ DONE (exit)
```

---

## Database Persistence

Once saved, session in database:

```sql
SELECT id, phase, week, created_at FROM training_sessions 
WHERE phase = 'phase 2' AND week = 5;

-- Output:
-- id: a1b2c3d4-...
-- phase: phase 2
-- week: 5
-- created_at: 2025-02-16T12:30:45.123456
```

Raw JSON stored in `raw_json` column.

---

## Next Features (Phase 6+)

- **History Integration:** Show last exercise before building new one
- **Edit Mode:** Reopen saved session to modify
- **Batch Log:** Quick notation for multiple sets
- **Voice Input:** Audio logging (future)
- **Analytics:** View progression on exit
