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
| `adhoc_movement_skills_session.md` | Ad-hoc, no program/phase/week — juggling (skill-run catches), reaction drill (attempt-count reps with ms in notes), L-sit holds (duration) |
| `adhoc_calisthenics_rings_session.md` | Ad-hoc, no program/phase/week — ring support hold (duration), muscle-up transition attempts (full/partial clean-vs-failed), ring dips (plain reps despite varying quality — regression case for not misreading quality commentary as partial reps) |
| `programmed_calisthenics_mixed_session.md` | Calisthenics mixed into a real phase/week program alongside normal weighted lifts — confirms movement-skill conventions and formal program extraction work together, AI-parser only (see note below) |
| `adhoc_remarks_and_session_notes.md` | Free-prose remarks blocks: pre-exercise remarks with no named movement (→ session-level `notes`), an exercise-level RPE range stated once after 4 identical sets (→ last set only, not all four), and a remark naming a specific set ("Top set RPE 9") overriding the last-set default. AI-parser only. |
| `programmed_push_pull_session_with_remarks.md` | Real 6-exercise push/pull session (originally `inputs/sessions/test_session_asif.txt`, dates bumped to year 3000) — phase/week stated with no program name, a `"Movement:"` label (no longer a focus alias — should be ignored or fall through to notes, never crash or overwrite focus), warmup+cooldown block-level remarks, and 6 exercises each with their own remarks block. The regression case that surfaced the provider-temperature non-determinism bug: same file, `--parser groq`, produced different extractions across repeated calls before `temperature=0` was pinned. AI-parser only. |

**AI-parser only:** the movement-skill and remarks/session-notes fixtures above only work
with `--parser ai` or `--parser groq` — the deterministic `rules` parser has no concept of
skill-run counts, holds recorded as bare `Ns`, attempt/clean phrasing, or remark-block
attachment, and will raise on them. See `src/traininglogs/agent/prompts.py`'s
`SYSTEM_PROMPT` for the extraction conventions these fixtures exercise, and
`movement-skill-plan.md` / `refactor-data-model.md` for the full design record.

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
