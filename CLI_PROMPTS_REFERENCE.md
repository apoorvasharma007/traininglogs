# New CLI Prompt Functions Reference

This document describes the new prompt functions added to `src/cli/prompts.py` that support the refactored agent-based CLI.

---

## Function 1: `show_exercise_context(context)`

**Purpose:** Display exercise history and AI suggestions to the user.

**Parameters:**
- `context: LoggingContext` - Object from `agent.prepare_exercise_logging()`

**What LoggingContext contains:**
```python
class LoggingContext:
    exercise_name: str                    # e.g., "Bench Press"
    is_new_exercise: bool                 # True if no history
    last_weight: Optional[float]          # e.g., 100
    last_reps: Optional[int]              # e.g., 5
    last_rpe: Optional[int]               # e.g., 8
    max_weight: Optional[float]           # e.g., 115
    suggested_weight: Optional[float]     # e.g., 102.5
    suggested_reps_range: Optional[tuple] # e.g., (4, 6)
    days_since_last: Optional[int]        # e.g., 3
```

**Example Output (New Exercise):**
```
📋 Logging: Squat
==================================================
✨ New exercise - no history to reference
```

**Example Output (Existing Exercise):**
```
📋 Logging: Bench Press
==================================================
📚 Last: 100kg (logged 3 days ago)
⭐ Max ever: 115kg
💡 Suggested: 102.5kg
   Rep range: 4-6 reps
```

**Usage in CLI:**
```python
context = agent.prepare_exercise_logging("Bench Press")
prompts.show_exercise_context(context)
```

---

## Function 2: `prompt_sets(set_type, suggested_count, suggested_weight, suggested_reps_range)`

**Purpose:** Interactively collect set data (weight, reps, RPE) with AI suggestions.

**Parameters:**
- `set_type: str` - Either "warmup" or "working"
- `suggested_count: int` - Default number of sets (default: 1)
- `suggested_weight: float` - AI-suggested weight (optional)
- `suggested_reps_range: tuple` - AI-suggested rep range as (min, max) (optional)

**Returns:**
```python
list[dict]  # [{'weight': X, 'reps': Y, 'rpe': Z}, ...]
```

**Example Output (Warmup):**
```
WARMUP SETS
----------------------------------------
Number of warmup sets? [2]: 

Warmup Set #1
  Weight (kg) [102.5]: 90
  Reps [4-6]: 5
  RPE (1-10) [skip if warmup]: 

Warmup Set #2
  Weight (kg) [102.5]: 100
  Reps [4-6]: 3
  RPE (1-10) [skip if warmup]: 5
```

**Example Output (Working):**
```
WORKING SETS
----------------------------------------
Number of working sets? [1]: 3

Working Set #1
  Weight (kg) [102.5]: 102.5
  Reps [4-6]: 5
  RPE (1-10) [skip if warmup]: 8

Working Set #2
  Weight (kg) [102.5]: 102.5
  Reps [4-6]: 5
  RPE (1-10) [skip if warmup]: 8

Working Set #3
  Weight (kg) [102.5]: 102.5
  Reps [4-6]: 5
  RPE (1-10) [skip if warmup]: 8
```

**Usage in CLI:**
```python
warmup_sets = prompts.prompt_sets(
    "warmup",
    suggested_count=2,
    suggested_weight=context.suggested_weight
)

working_sets = prompts.prompt_sets(
    "working",
    suggested_count=1,
    suggested_weight=context.suggested_weight,
    suggested_reps_range=context.suggested_reps_range  # (4, 6)
)
```

**Behavior:**
- Shows defaults in square brackets `[default]`
- User can press Enter to accept default
- User can type custom value to override
- Weight and Reps are required
- RPE is optional
- If user enters nothing for required field, re-asks for that set

---

## Function 3: `confirm_action(action_text)`

**Purpose:** Ask user to confirm an action with yes/no prompt.

**Parameters:**
- `action_text: str` - Description of action to confirm

**Returns:**
```python
bool  # True if user entered 'y', False otherwise
```

**Example:**
```python
if prompts.confirm_action("Save workout?"):
    # Save session
else:
    # Cancel
```

**Example Output:**
```
Save workout? (y/n): y
```

---

## How They Work Together in CLI

### Complete Flow Example

```python
# 1. Get session metadata
metadata = prompts.prompt_session_metadata()

# 2. Agent creates session
session = agent.prepare_workout_session(
    phase=metadata["phase"],
    week=metadata["week"],
    focus=metadata["focus"],
    is_deload=metadata["is_deload"]
)

# 3. Enter exercises
exercise_name = prompts.prompt_exercise_name(1)

# 4. Agent prepares context (queries history, suggests progression)
context = agent.prepare_exercise_logging(exercise_name)

# 5. SHOW CONTEXT TO USER ← NEW!
prompts.show_exercise_context(context)
# Shows: last weight, max weight, suggested weight, suggested reps

# 6. GET SETS WITH SUGGESTIONS ← NEW!
warmup_sets = prompts.prompt_sets(
    "warmup",
    suggested_count=2,
    suggested_weight=context.suggested_weight
)

working_sets = prompts.prompt_sets(
    "working",
    suggested_count=1,
    suggested_weight=context.suggested_weight,
    suggested_reps_range=context.suggested_reps_range
)

# 7. Agent validates and adds
success, error = agent.log_exercise(
    session,
    exercise_name,
    warmup_sets,
    working_sets
)

# 8. Repeat or finish
if prompts.prompt_continue_session() == 'a':
    # Go to step 3
else:
    # Continue to step 9

# 9. Finalize
agent.finalize_workout(session)

# 10. Save
if prompts.confirm_save():  # ← Uses confirm_action logic
    db_repo.save_session(session.id, session.to_dict())
    exporter.export_session(session.to_dict())
```

---

## Design Philosophy

### Why These Functions?

1. **`show_exercise_context()`**
   - Gives user visibility into their history
   - Shows AI suggestions without forcing them
   - Provides context for informed decisions

2. **`prompt_sets()`**
   - Interactive with smart defaults
   - User can accept suggestions (faster entry)
   - User can override if they know better
   - Handles both warmup and working sets
   - Validates required fields

3. **`confirm_action()`**
   - Yes/no prompts
   - Consistent with other prompt functions
   - Simple and clear

### Smart Prompting Strategy

```
Show context
    ↓
Show suggestions
    ↓
User decides (accept or override)
    ↓
Optional: show reasoning (if requested)
    ↓
Log exercise
```

This approach:
- ✅ Is guided but not restrictive
- ✅ Respects user expertise
- ✅ Accelerates data entry for common cases
- ✅ Provides learning (users see patterns)

---

## Error Handling

### `prompt_sets()` Validation

If user enters invalid data:

```
Weight required?
❌ Required

Reps?
❌ Required

RPE?
✅ Optional (can skip)
```

If user enters nothing for required field, the function:
1. Shows error message
2. Doesn't increment set counter
3. Re-asks for that set

---

## Future Enhancements

### Phase 2: Extended Suggestions
- Show reasoning for suggested weight
  ```
  💡 Suggested: 102.5kg
     Reasoning: RPE was 8, increasing by 2.5kg
  ```

### Phase 3: Pattern Recognition
- Suggest based on weekly pattern
  ```
  📊 Pattern: You typically do 3×5 on Mondays
  💡 Suggested sets: 3
  ```

### Phase 4: Voice Input
- Voice to text for sets entry
  - "Weight 100, reps 5, RPE 8"

---

## Testing the New Functions

### Quick Test
```bash
python -c "
import sys
sys.path.insert(0, 'src')
from agent import LoggingContext
from cli import prompts

# Create test context
context = LoggingContext(
    exercise_name='Bench Press',
    is_new_exercise=False,
    last_weight=100,
    last_reps=5,
    last_rpe=8,
    max_weight=115,
    suggested_weight=102.5,
    suggested_reps_range=(4, 6),
    days_since_last=3
)

# Test show_exercise_context
prompts.show_exercise_context(context)
# Should print context with history

# Test confirm_action
# prompts.confirm_action('Test action?')  # Would wait for user input
"
```

### Full CLI Test
```bash
python -m src.cli.main
# Follow prompts, watch new context display in action
```

---

## Summary

| Function | Purpose | Parameters | Returns |
|----------|---------|-----------|---------|
| `show_exercise_context()` | Display history & suggestions | `LoggingContext` | None (prints) |
| `prompt_sets()` | Get sets with smart defaults | set_type, count, weight, reps_range | `list[dict]` |
| `confirm_action()` | Yes/no confirmation | action_text | `bool` |

These three functions enable **smart, interactive prompting** that makes the CLI user-friendly while keeping the code clean and maintainable. ✨
