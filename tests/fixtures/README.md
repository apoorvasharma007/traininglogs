# Test fixtures

Sample sessions for testing the AI extraction. Each file in `valid/` is a session written the
way a person types it, picked because it gives the model something specific to get right. Every
date is in the year 3000, so nothing here can collide with a real session.

`scripts/eval_ab.py` reads four of them by default, marked below. Pass any others with
`--files`. The pytest suite doesn't read these files.

| File | What it tests |
|---|---|
| `strength_session.md` | The basics: one exercise with warmup sets, a goal with a rep range, RPE and rest |
| `standalone_session.md` | The bare minimum: no program, phase or week, one bodyweight exercise |
| `activity_session.md` | Sets measured in duration, distance and heart rate instead of weight |
| `unilateral_session.md` | Left and right reps counted separately, with partial reps per side |
| `deload_session.md` | A deload week, lighter loads, bodyweight pull-ups at 0 kg |
| `push_long_session.md` | A real push session with 10 exercises, myo-reps, bodyweight work, empty warmup sections and cues |
| `lower_strength_session.md` | A real lower session with lengthened partials and static holds, ramping warmups, and some sets without RPE |
| `adhoc_movement_skills_session.md` | Skills: juggling catches, a reaction drill counted in attempts, L-sit holds in seconds. Eval default. |
| `adhoc_calisthenics_rings_session.md` | Rings: support holds, muscle-up attempts split into clean and failed, and dips where comments about quality must not be read as partial reps. Eval default. |
| `programmed_calisthenics_mixed_session.md` | Calisthenics skills inside a program week, next to weighted lifts |
| `adhoc_remarks_and_session_notes.md` | Free remarks: a remark that belongs to the whole session, an RPE stated once for four sets (it goes on the last set only), and "Top set RPE 9" pointing at one set. Eval default. |
| `programmed_push_pull_session_with_remarks.md` | A real six-exercise push/pull session with a phase and week but no program name, a `Movement:` label that must not overwrite the focus, and remarks on every block. Eval default. |

When a change to the prompts or schema is meant to handle a new kind of input, add a fixture
for it here with a year-3000 date.
