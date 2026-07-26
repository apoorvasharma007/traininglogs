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

## Extension: templates + gym/calisthenics mix (2026-07-19, same day)

Apoorva's real training includes calisthenics/gymnastics-rings work in three
shapes: (1) gym sessions mixing calisthenics with normal weights inside a real
phase/week program, (2) ad-hoc gym calisthenics/mobility/skill days, (3) ad-hoc
home rings/calisthenics/skill days. Location does not determine program — only
"is this part of a formal program" does, and that's already handled by
phase/week. Initial approach mistakenly split by location (new "calisthenics"
program vs "home-movement"); corrected after Apoorva's clarification, before
anything was committed.

- [x] 8. Copy-pasteable templates: `templates/home-movement-template.md` (blank,
       format legend for 5 movement shapes) + `templates/home-movement-example.md`
       (juggling/reaction/L-sit/shadow-boxing/KB flavor) — shipped `50bdd9c`.
- [x] 9. Extended SYSTEM_PROMPT: skill-attempt convention (muscle-up-style tries —
       clean completions → `rep_count.full`, failed tries → `rep_count.partial`,
       mirroring how a normal working set already distinguishes full vs partial
       reps). Fixed a real gap: sessions with `phase`/`week` but no stated program
       name were at risk of being defaulted to `"home-movement"` — tightened so
       `program` is left unset in that case instead (a phase/week session belongs
       to a real program whose name lives in the file path, not the text).
- [x] 10. `templates/home-movement-example-rings.md` — second ad-hoc worked
        example (rings/muscle-up-prep flavor: support hold, false-grip hang,
        muscle-up transition attempts, ring dips, weighted pull-up, hollow hold).
        `templates/gym-mixed-calisthenics-example.md` — worked example of
        calisthenics mixed into a real phase/week gym session (bench press, ring
        dips, ring muscle-up transition, DB shoulder press) using Apoorva's
        existing real gym-log format. Both validated end-to-end against the real
        Groq parser.
- [x] 11. Tests: added `test_skill_attempt_clean_vs_failed_maps_to_full_partial`,
        `test_movement_skill_exercise_valid_with_formal_phase_and_week`, and 2
        prompt-guard tests to `tests/test_home_movement.py` (16 tests total, up
        from 9). CHANGELOG and `docs/design.html` conventions paragraph rewritten
        to describe the corrected (location-agnostic) scope.
- [x] 12. Full suite green, squash-merged to `dev`.

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
