# Home-movement intake plan — COMPLETE

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
- [x] 1. Scaffolding: `inputs/programs/home-movement/program.md` with alias frontmatter
- [x] 2. SYSTEM_PROMPT conventions: skill runs = sets with rep_count (catches),
       holds/rounds/stretches = duration_seconds, reaction times verbatim into set
       notes, home-session program default `home-movement`. Tightened mid-session
       after E2E surfaced a real bug: reaction-drill attempt counts ("20 taps") were
       being read as duration_seconds. Fixed by explicitly distinguishing attempt
       counts (rep_count) from elapsed-time blocks (duration_seconds).
- [x] 3. Fixture: `tests/fixtures/home_movement_session.md` (realistic free text —
       juggling, reaction drill, L-sit holds, shadow boxing, ab-strap core, KB swings)
- [x] 4. Tests: `tests/test_home_movement.py` — 9 model-contract + prompt-content
       regression-guard tests, all passing
- [x] 5. Suite green: 349 passed, 0 skipped, 0 failed (docker test DB). E2E via
       `traininglogs validate tests/fixtures/home_movement_session.md --parser groq`
       against the real Groq parser — verified twice (before and after the
       reaction-drill fix)
- [x] 6. CHANGELOG [Unreleased] + design.html conventions note (design.html date
       bumped to 2026-07-19)
- [x] 7. Squash-merged to `dev` (`ed68648`), pushed to origin

## Known follow-ups (not blockers, not done here)

- **RPE over-propagation observed during E2E, not caused by this feature.** The
  fixture stated "RPE like 8 on the last one" (of 5 L-sit holds); the Groq parser
  extracted `rpe=8.0` on all 5 sets, not just the last. This is general LLM
  extraction behavior, unrelated to the home-movement conventions added here —
  worth a look if it recurs on real sessions, but out of scope for this branch.
- `scripts/spot_check_ai_parser.py` — an untracked leftover from a prior session's
  working tree, unrelated to this feature. Left untouched; Apoorva should decide
  whether to commit or discard it.
- Reaction time still has no chartable score field (deferred per the "no model
  change yet" decision) — revisit once enough reaction sessions exist to want a
  trend line.

## ▶ Resume here

Feature complete and merged to `dev` @ `ed68648`. Next real session: log an actual
home-movement workout for real (`traininglogs log <file> --parser groq`, or
`--parser ai` for the Anthropic default) and see how the conventions hold up against
real handwriting/phrasing, not just this fixture.
