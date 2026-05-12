# Test fixtures

Session markdown files for manual E2E testing. Organised into `valid/` (should parse
and insert cleanly) and `invalid/` (should fail at a specific stage with a known error).

All dates use year 3000 to guarantee no collision with real historical session IDs.

Automated tests (`pytest tests/`) do not import these files — they use inline `tmp_path`
fixtures. These files are for `traininglogs validate` (no DB write) and
`traininglogs log --no-commit` (DB write, no git) E2E workflows.
See `.claude/testing-guide.md` for the full E2E protocol.

---

## valid/

| File | What it covers |
|---|---|
| `strength_session.md` | Minimal bilateral strength — one exercise, warmup, goal with rep range, RPE, rest |
| `activity_session.md` | Activity sets — duration, distance, heart rate |
| `unilateral_session.md` | Unilateral reps with partial reps per side |
| `push_long_session.md` | Real-world push session: 10 exercises, myo-rep failure, bodyweight (0 kg), empty warmup sections, cues blocks |
| `lower_strength_session.md` | Real-world lower session: llp and statichold failure techniques, progressive warmups, missing RPE on some sets |
| `deload_session.md` | Deload week (`Deload: Yes`), lighter loads, bodyweight pullups (0 kg) |

When adding a new parser feature or session type, add a fixture here that exercises it.
Copy from a real input in `inputs/programs/`, change the date to `3000-MM-DD`, and strip
any personally identifiable notes if needed.

---

## invalid/

Each file is designed to fail at a specific stage. Use `traininglogs validate <file>` to
confirm the failure and error message before relying on it in testing.

| File | Stage | Expected failure |
|---|---|---|
| `missing_date.md` | Parser — `build_training_session` | `ValueError`: date field missing from metadata |
| `malformed_set_line.md` | Parser — `_parse_working_set_line` | `ValueError`: line does not match set format |
| `rpe_out_of_range.md` | Model validation — Pydantic | `ValidationError`: RPE must be 1–10 in 0.5 steps |
| `malformed_goal.md` | Parser — `_parse_goal` | `ValueError`: goal string does not match expected pattern |
| `missing_focus.md` | Parser — `build_training_session` | `ValueError`: focus field missing from metadata |

Add a new invalid fixture whenever a new validation rule or parser constraint is added.
The fixture documents the constraint and gives future developers a reproducible failure case.
