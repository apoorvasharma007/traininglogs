# Home-movement intake plan

## Goal

Log home/movement-general training (calisthenics, juggling, reaction drills, shadow
boxing, parallettes, ab-strap core, stretching, KB/DB home lifts) through the existing
free-text LLM intake, with zero data-model changes. Decisions locked 2026-07-19 in
discussion with Apoorva: hybrid insight (consistency + hard metrics where natural);
catches = reps, holds = duration_seconds, home lifts = weight × reps, reaction ms =
set notes (no score field yet); grouping = umbrella program `home-movement` with no
phase/week, `focus` names the day's domain; capture = free text via LLM extract.

## Blast radius

- `inputs/programs/home-movement/program.md` — new (dashboard program card)
- `src/traininglogs/agent/llm_parser.py` — SYSTEM_PROMPT additions only
- `tests/fixtures/home_movement_session.md` — new fixture
- `tests/test_home_movement.py` — new tests (model-contract level)
- `CHANGELOG.md` — [Unreleased] entry
- `docs/design.html` — data-model conventions note
- No changes: models, parser (rules), processor, DB schema, API, dashboard code

## Steps

- [x] 0. Carry over prior session's uncommitted work as labeled commits
       (`a244b14` design.html vision section, `352c93c` prompt warmup/cooldown fix)
- [ ] 1. Scaffolding: `inputs/programs/home-movement/program.md` with alias frontmatter
- [ ] 2. SYSTEM_PROMPT conventions: skill runs = sets with rep_count (catches),
       holds/rounds/stretches = duration_seconds, reaction times verbatim into set
       notes, home-session program default `home-movement`
- [ ] 3. Fixture: `tests/fixtures/home_movement_session.md` (realistic free text)
- [ ] 4. Tests: model-contract tests cementing what this feature relies on
       (program w/o phase+week; duration-only sets; rep-only sets; session_id for
       non-phase paths)
- [ ] 5. Suite green (docker test DB), E2E: `traininglogs validate <fixture> --parser groq`
- [ ] 6. CHANGELOG [Unreleased] + design.html conventions note
- [ ] 7. Apoorva review → squash-merge to dev

## ▶ Resume here

Branch `feature/home-movement-intake` (cut from dev @ 58d54e1). Step 0 done.
Next: Step 1 scaffolding.
