# Movement-skill intake plan — COMPLETE

(Renamed from `home-movement-plan.md` — see Extension 2 below. The "home-movement"
pseudo-program was removed in that pass; ad-hoc sessions now leave `program` unset
entirely and live at `inputs/sessions/`.)

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

## Extension 2: pipeline confusion cleanup — remove "home-movement" pseudo-program (2026-07-19, same day)

Apoorva pointed out two real problems after using the shipped templates: (1) it
wasn't clear where ad-hoc sessions were supposed to live in the pipeline —
`inputs/programs/home-movement/` blurred the line between "real structured
program" and "no program at all," when the codebase already had an established,
tested "standalone" concept (`program=None`, `tests/test_processor.py`) and an
empty `inputs/sessions/` directory clearly meant for it but never documented; and
(2) template/fixture naming didn't communicate which of his 3 real use cases each
file was for. Also requested: reorganize `pytest` fixtures to mirror real input
shape with valid/invalid encoded in the filename — turned out `tests/fixtures/`
already had an established `valid/`/`invalid/` convention (with its own README,
year-3000 dates, "pytest does not import these, they're for manual E2E" rule) that
the earlier `tests/fixtures/home_movement_session.md` had broken by not following.

Resolution, confirmed via one clarifying question (drop the dashboard "Program"
card for ad-hoc sessions and use `inputs/sessions/` with `program=None`, vs. keep
a card under a better-named `inputs/programs/<name>/` — chose the former):

- [x] 13. Removed `inputs/programs/home-movement/` entirely. Ad-hoc sessions now
        leave `program`/`phase`/`week` all unset — no pseudo-program name invented.
        `SYSTEM_PROMPT` simplified to match (one rule: no program+no phase/week →
        ad-hoc, leave all three unset; phase/week without a stated name → still
        leave `program` unset, unchanged from Extension 1's fix).
- [x] 14. `inputs/sessions/README.txt` added (named `.txt`, not `.md`, so a bulk
        `traininglogs log inputs/sessions/` glob never ingests it) documenting the
        convention: `inputs/sessions/` for ad-hoc, `inputs/programs/` stays real
        structured programs only.
- [x] 15. Templates renamed to name the use case directly: `adhoc-template.md`
        (blank, no `Program:` field — ad-hoc sessions don't have one anymore),
        `adhoc-example-home-skills.md`, `adhoc-example-gym-calisthenics.md`,
        `programmed-example-calisthenics-mixed.md` (unchanged content — this one
        was never mislabeled, since it already relied on `Phase`/`Week`, not a
        program name).
- [x] 16. Test fixtures moved into the existing `tests/fixtures/valid/` convention:
        `adhoc_movement_skills_session.md`, `adhoc_calisthenics_rings_session.md`,
        `programmed_calisthenics_mixed_session.md` (year-3000 dates, matching
        style). `tests/fixtures/README.md` table + an "AI-parser only" note added.
        No new `invalid/` fixtures — this work introduced no new Pydantic
        constraint, only prompt-level conventions.
- [x] 17. Real bug caught during fixture E2E validation (Groq): "6 reps - depth
        dropped off on last two" was misread as `full=4, partial=2` — the new
        skill-attempt convention (Extension 1) was bleeding into ordinary rep
        counting whenever notes mentioned some reps differing from others.
        Tightened the prompt: skill-attempt full/partial only triggers on
        explicit attempt/clean/tries phrasing; quality commentary on ordinary
        reps must never move reps into `partial`. Reverified — both conventions
        now fire correctly side by side in the same session.
- [x] 18. `tests/test_home_movement.py` replaced by
        `tests/test_movement_skill_conventions.py` — program assertions updated
        (`None` instead of `"home-movement"`), added a regression test for the
        full/partial bleed bug, added a prompt-guard test for the new
        disambiguation rule. 18 tests total (up from 16).
        `home-movement-plan.md` renamed to `movement-skill-plan.md`.
        CHANGELOG and `docs/design.html` conventions paragraph rewritten again to
        describe the final architecture (no pseudo-program, `inputs/sessions/`).
- [x] 19. Full suite green, squash-merged to `dev`.

## Known follow-ups (not blockers, not done here)

- **RPE over-propagation observed during E2E in Extension 1, not caused by this
  feature.** The original loose-prose fixture stated "RPE like 8 on the last one"
  (of 5 L-sit holds); the Groq parser extracted `rpe=8.0` on all 5 sets, not just
  the last. Did not reproduce on the structured template/fixture versions —
  general LLM extraction behavior on loose phrasing, not a systematic bug. Watch
  on real sessions, don't chase yet.
- `scripts/spot_check_ai_parser.py` — an untracked leftover from a prior session's
  working tree, unrelated to this feature. Left untouched; Apoorva should decide
  whether to commit or discard it.
- `ANTHROPIC_API_KEY` in traininglogs `.env` was rejected (401, "API key is
  invalid") when tested in Extension 1 — Groq stood in for all E2E verification in
  this plan, but the actual default path (`traininglogs log`, no `--parser` flag)
  is unverified until the key is fixed.
- Reaction time still has no chartable score field (deferred per the "no model
  change yet" decision) — revisit once enough reaction sessions exist to want a
  trend line.

## ▶ Resume here

Feature complete and merged to `dev`. Ad-hoc sessions: copy `templates/adhoc-template.md`
into `inputs/sessions/<date>.md`, fill it in, `traininglogs log inputs/sessions/<date>.md`.
Calisthenics mixed into a real program: just add it as another exercise in that
program's existing phase/week file — no separate template. Next real session: log an
actual workout for real and see how the conventions hold up against real
handwriting/phrasing, not just the fixtures. If `ANTHROPIC_API_KEY` is fixed, worth
one validation run with `--parser ai` (the real default) instead of `--parser groq`.
