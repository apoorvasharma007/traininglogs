# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Staging: a practice copy of the app and database. A push to `dev` deploys it; `main` still
  deploys production.

### Changed

- Row-level security is on for every table, with no rules, so Supabase's automatic web API can't
  read or change any row. The server is unaffected.

## [4.1.0] - 2026-10-05

### Added

- Program templates: New program offers "Create your own" or "From a template". Four starter
  templates (5×5 strength, Push / pull / legs, Upper / lower, Upper / lower / PPL) show their
  workouts, and "Add program" copies one into your programs. The server lists them at
  `GET /templates` and copies one with `POST /templates/{id}/copy`.
- An empty workout has an Add exercises button that starts editing, instead of "Tap Edit to add
  some".
- Move up and Move down in a session's exercise menu. If the order changed, "Update the
  program?" offers "Change the order", unticked; exercises you skipped keep their place.
- The empty Programs screen has a New program button instead of an explanation.

### Fixed

- An exercise's menu no longer has "Add set"; the card's + Set does the same, in the session and
  the confirmation card.
- Every screen's main action sits in a bar fixed at the bottom: Start workout, Follow this
  program, Read my note, Confirm session, Save changes, Done. Before, some sat right after the
  content, near the top on a short screen.
- Sheets open as tall as their content, up to the visible screen, so a long menu no longer needs
  scrolling on a normal iPhone. Before, they stopped at 80% of Safari's full height.
- Settings no longer says "Choosing your own key lifts comes later."
- Progress tiles say "Not logged yet" for a lift never logged, and "No sets with an RPE yet · 3
  sessions" for one logged without RPE, instead of "No countable sets yet" for both.
- The Done screen survives the app restarting on it: the summary and the "Update the program?"
  offer come back. Before, it said "Nothing just finished" and the offer was lost.
- Estimated max now counts only sets with an RPE. Before, a set without one was treated as all
  out, which understated the max whenever reps were left. A session with no RPE shows on the
  lift's chart as a hollow dot at its heaviest weight, and in its session list as "heaviest, no
  RPE"; it doesn't count toward the latest, best or trend.
- Safari on iPhone zoomed the page in when you tapped a small box or double-tapped. The app now
  stays at its normal size.
- The confirmation card's top shows three rows, Date, Workout and Duration, each one tappable to
  change it. "Not part of a program" sits in the workout list, replacing the "Was this ...? No"
  sentence.
- Error messages say what went wrong and what to do. A server error shows its code ("Server
  error (500). Try again in a minute."), a lost connection says "No connection", and a note that
  couldn't be read says it's still saved. Before, some showed raw technical text.
- Confirming a note that's already saved says so ("This note is already saved as a session. Find
  it in History.") instead of a database error that told you to change the date.
- After a session, "Update the program?" matches each exercise and movement to the one in the
  workout it started from instead of by name. A renamed exercise shows as one line ("Squat → Squats"),
  unticked, so a typo can't reach the program by accident. Switching to an alternative offers to
  make it the main exercise. Extra sets count only once ticked, and an exercise added but never
  done isn't offered. A skipped warm-up or cool-down movement from the workout is offered for removal, and
  a different amount ("Easy cardio: 10 min (was 5 min)") as a change.
- The exercise editor's alternatives are headed "Alternatives · switch during the workout"
  instead of "Or".
- The exercise editor's reps hint says "Leave empty for AMRAP (as many reps as possible)".
- The deload reminder sheet says "Remind me to take a lighter week after this many weeks of
  training" instead of "Suggest a lighter pass through the program".
- The home screen's next-workout card is a summary: program name, workout name and exercise
  names. The "Current program" and "Next workout" labels, sets and alternatives are gone; they
  show once the workout starts.
- Log from notes gives the real cost in rupees: about ₹2 to ₹5 to read a note, and ₹1 to ₹3 for
  each AI fix after that. It said "about 3 cents".
- Log from notes' button says "Read my note" instead of "Extract".
- The waiting-to-send bar's button says "Send now" instead of "Retry".
- After a session, the offer to change the workout is called "Update program" at every step.
  Before, it was "Save to program" on the button and "Update program" in the confirm.
- "Remove" is used for taking a set, exercise or workout out, and "Delete" only for a whole
  program. The confirmation card's Undo bar says what was removed ("Squat removed").
- "Warm-up" is spelled the same everywhere; some places said "Warmup".
- Warm-up set templates say they build up to your first working set, and show greyed out with
  how to use them when that set has no weight yet. Before, they were hidden.
- When an AI fix can't be used, the fix box now says why in plain words, naming the exercise and
  sets ("Face pull, warm-up sets 1 and 2: needs a weight."), and keeps your message. Before, a
  red bar showed the server's raw error.
- The AI fix box asks for every change in one message, says each fix is a paid AI call, and
  cycles through longer examples.
- Values the AI marked unsure for every set of an exercise ("exercises.0.sets.*.reps") weren't
  passed to the card.
- A session shorter than a minute failed to save (a duration of 0) and waited to send forever.

### Changed

- Alternatives no longer take turns: a workout starts with the first exercise, and a swap icon
  beside its name switches the session to an alternative, refilled from that one's last time.
- Target reps is one field; empty means as many as you can.
- A workout's name field starts as "Workout N"; adding a workout asks for its name.
- Deleting an exercise from a program's workout asks first.
- A set with a note shows a note marker on its row. Train no longer has "Do a different workout".
- Program and workout screens open for viewing; Edit shows renaming, reordering, adding and
  settings. The workout's title is its name, edited in place.
- Effort in words: Moderate, Hard or All out, stored as RPE 7, 8.5 or 10; an exact RPE stays one
  tap away. Set rows show effort as a small three-bar meter.
- Warm-up ramps from an exercise's menu: Full ramp, Short ramp, 5/3/1 style or one feeler set,
  worked out from the first working set's weight.
- The session's LAST column is gone; last time shows in the boxes and in the set's drawer.
- Warm-up and cool-down for the whole session: a program's workout can carry them, a session copies
  them at Start, and only ticked ones are saved. Presets: General, Upper body, Lower body; Walk and
  stretch, Stretch only. `PUT /workouts/{id}/movements`; `POST /sessions` takes `warmup` and
  `cooldown`; `program_workouts.warmup` and `.cooldown`.
- The 40/50/60% warm-up ramp is called Wendler's 5/3/1. Bodyweight sets get no ramp.
- Warm-up and cool-down drawers are headed "templates"; the exercise ramp menu item is "Warm-up
  set templates" and warns only before replacing warm-up sets you entered. Templates: Easy cardio
  and Dynamic stretching to warm up, Easy cardio and Static stretching to cool down.
- After a session from a program, "Save changes to the program?" lists how it differed: more sets,
  new exercises and new warm-up or cool-down movements start ticked; removed exercises and fewer
  sets start unticked. Skipped sets and alternatives are not changes. Replaces the all-or-nothing
  "Update workout?".
- The set drawer keeps its height when switching to Warmup, so the switch stays under your finger.
- Review shows what the AI wasn't sure of as amber boxes, with "N things to check" to jump to
  them; an exercise it couldn't read says so plainly. The header is the date, "Was this Workout 3
  of Starting Strength?" and the duration. The fix box asks for changes in plain words, with
  examples that change every few seconds.
- A session is named after its workout, or after its first exercises; History uses that name.
- "Do this again" on a past session starts it as a live session. Home: the next workout, a "Wrote
  it down instead?" card for Log from notes, then Repeat a past session and Ad-hoc workout
  (formerly Blank workout). Without a program, home offers recent sessions to do again.
- The deload reminder only reminds: OK hides it for another stretch of the program's weeks.
- Editing a program or a workout is a draft: renaming, reordering, exercises and warm-up or
  cool-down change nothing until Save changes; Cancel discards (asking first if anything changed).
  The tabs and back arrow hide while editing. The deload reminder's weeks are chosen, then saved.
- Review matches the session screen: no NOTE column (effort and notes show beside the set number),
  and the date is a quiet line that opens the date picker.
- Saving changes to a program, stopping following, and following a program while another is
  followed each ask first.
- A session starts with "Warm up first · 5 min easy cardio": Start runs a countdown and records it
  when it ends (or on Done); ✕ skips it. The deload reminder is one line in weeks (3 to 8) at
  the foot of a program's page, beside Stop following.
- A set's drawer holds only what its row can't: warmup or working, RPE, note, delete. Weight and
  reps are typed on the row. The deload reminder and Stop following show on the program's page.
- In a session, an exercise collapses to one line when its last set is ticked, the next one
  scrolls into view, and the header shows the exercise you're on.


## [4.0.0] - 2026-10-04

### Removed

- The old one-page web UI (`web/`). The React app replaces it at `/`; `/app/` redirects there.
- The "Repeat a past session" screen. `POST /sessions/{id}/repeat` stays.


### Added — Phase 8 step 6b, choices in a workout's plan

- A plan line can list other exercises that can take its place ("Shoulder Press or Bench
  press"). Starting the workout picks the one done longest ago, so they take turns; the session
  shows just that one and can still change anything. Renaming suggests the line's choices.
- `program_workout_exercises.alternatives`.
- `scripts/add_starting_strength.py` adds Starting Strength Phase 4 as three workouts with
  choices, links the sessions logged under it, and follows it.

### Added — Phase 8 step 6, the Train home screen

- Train shows the program you follow and its next workout with Start, or the session in
  progress with Resume, plus Blank workout and Log from notes, and how many finished sessions
  are waiting to send.
- A one-line deload reminder when a program reaches its deload days (28 by default). Start makes
  the next pass through the program a deload; ✕ hides the reminder for 7 days.
- `GET /programs` reports each program's deload count.

### Fixed

- The API replaces database connections the server has closed; before, every request failed
  until a restart after Supabase dropped idle connections.

### Added — Phase 8 step 5, logging a session in the app

- Start a workout from a program, or a blank one. Last time's weights and reps fill in grey;
  tick each set as you do it; add sets, warmup sets and exercises; pin a note to an exercise.
- The session is saved on the phone (IndexedDB) on every change and sent once at Finish. Offline,
  it waits on the phone and sends itself when the connection returns.
- `POST /sessions` saves a session with no model call; `GET /exercises/last` gives last time.
- Finish offers to update the workout's plan when the session differed from it.
- Weight and reps are boxes on each set row, on the session screen and on Review; the set number
  opens a drawer for warmup or working, RPE, note and delete.
- `scripts/copy_prod_to_dev.py` copies production into a local `traininglogs_dev` database (prod
  is only read), to try the app on real data; `scripts/add_bts_programs.py` adds Bodybuilding
  Transformation as two programs, Foundation and Ramp-up, from the sessions already logged.

### Fixed

- A drawer opened from a set didn't slide into view until something else on screen changed.

### Changed

- Raw input kinds are `text` (a note the model reads) and `manual` (entered in the app, no model
  call), replacing `markdown` and `repeat`; `photo` and `speech` were never used and are gone.

### Added — Phase 8 step 4, the Programs tab

- Programs list, a program's workouts (drag to reorder, follow, deload reminder, rename, delete)
  and a workout's plan (name, exercises with warmup sets, working sets and target reps or as many
  as you can, drag to reorder).
- Review asks which workout a pasted session counts as; `POST /extractions/{id}/confirm` takes
  `program_workout_id`.
- Sheets are now the shadcn Drawer (drag to close); the lift chart uses Recharts; Motion drives
  reordering. Only the Train screen is in the first download (81 KB); other screens load when
  opened, and the tabs are fetched in the background.

### Added — Phase 8 step 3, programs in the database

- Tables `programs`, `program_workouts`, `program_workout_exercises` and `exercise_pins`, and
  `sessions.program_workout_id`. Only additions; no existing column or row changes.
- Endpoints to create, rename, follow, archive and reorder programs and workouts, set a
  workout's plan, and pin notes to exercises. A program reports its next workout: the one after
  its latest session, back to 1 after the last.

### Added — Phase 8 step 2, the current screens in React

- Progress (key lifts, other lifts, a lift's chart and sessions), History grouped by week with a
  read-only session view, Settings, Log from notes and Review.
- Review edits a set in a bottom sheet (±2.5 kg, ±1 rep, RPE, warmup or working, note), adds
  sets, warmup sets and exercises from a ⋯ menu, and undoes a removal. It uses the existing
  `/edit`, `/correct` and `/confirm` endpoints.
- Charts are drawn as SVG instead of with a chart library; first-load JavaScript is 89 KB.

### Added — Phase 8 step 1, the React app skeleton

- `frontend/`: React, TypeScript and Vite, with Tailwind, TanStack Query, wouter, Lucide and the
  Geist fonts. Five tabs (Train, Programs, Progress, History, Settings) with empty screens, and
  the light and dark colours from `react-plan.md`.
- The API serves the built app at `/app/`; the old UI stays at `/` until step 8. The Docker image
  builds the app in a Node stage.
- CI type-checks, lints, tests and builds the app. The build fails if first-load JavaScript passes
  120 KB gzipped (78 KB now).

### Added — Phase 7, a Progress tab with estimated max per lift

- The web app gets Log and Progress tabs. Progress lists six key lifts (Squat, Bench Press,
  Shoulder Press, Deadlift, Barbell Clean, Pull-up) and, under "Other lifts", every exercise
  trained in 3 or more sessions. Each lift opens a chart of its best estimated max per session,
  with record sessions marked, the goal weight as a line, and the sets behind each point.
- Estimated max = weight × (1 + (reps + RIR) / 30), RIR = 10 − RPE; plain Epley without RPE.
  Counted: working sets, weight above 0, 1 to 12 full reps; unilateral sets use the weaker side.
  Pull-up shows best reps at bodyweight and added weight separately.
- `analytics/strength.py`, `analytics/key_lifts.py`, `analytics/progress.py`;
  `GET /progress/lifts` and `GET /progress/lifts/{name}`. Charts use Chart.js 4.5.1 from cdnjs.

### Added — Phase 6, deployed to Google Cloud Run with Terraform and CI/CD

- The app runs on Cloud Run (`us-east1`, 512 MiB, 0–2 instances, inside the always-free tier):
  https://traininglogs-875429444117.us-east1.run.app
- `infra/`: Terraform (`modules/{project,app}`, `environments/prod/{project,app}`). Project layer:
  APIs, workload identity pool `github` (only this repository), service accounts `terraform` and
  `app-deploy` (`main` only). App layer: Artifact Registry `images` (keeps newest 2), secrets
  (values never in state), `app-runtime`, Cloud Run service `traininglogs`. State in a versioned
  bucket, the one manual step.
- `cd.yml`: after CI succeeds on `main`, waits for approval (GitHub environment `prod`), applies
  the app layer, then builds the image and deploys it to Cloud Run.
- Repository variables `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`,
  `GCP_TERRAFORM_SERVICE_ACCOUNT`, `GCP_APP_DEPLOY_SERVICE_ACCOUNT`.

### Changed — CI checks everything, on every change

- `ci.yml` runs on every pull request and push to `main` (no path filter — a `web/`-only change
  used to skip CI) and gains a `terraform` job: format, validate both layers, and plan
  `prod/app`, posted as one comment on the pull request.
- Actions on current majors: `checkout@v7`, `setup-python@v7`, `setup-terraform@v4`,
  `auth@v3`, `setup-gcloud@v3`, `github-script@v9`, `action-gh-release@v3`.

### Removed

- Scripts that belonged to the retired markdown flow or were one-off tools:
  `build_dashboard.py`, `import_sessions_to_db.py`, `regen_historical.py`,
  `regen_historical_ai.py`, `repopulate_db.py`, `validate_regen.py`, `validate_v3_local.py`,
  `apply_schema_supabase.py`, `test_supabase_connection.py`, `test_supabase_counts.py`,
  `measure_prefix_tokens.py`, `groq_limits.py`, with `tests/test_import.py`. Kept:
  `correction_stats.py`, `eval_arms.py` and `eval_ab.py`, which `eval_arms.py` imports.
- `tests/fixtures/invalid/`, which nothing read.
- `fly.toml` — the Fly plan was replaced by Cloud Run (Fly has no free tier).

### Added — the web UI is served by the API (deploy prep)

- The API serves `web/` at `/`, mounted after every API route, with `Cache-Control: no-cache`
  so a deploy is never hidden behind a cached `app.js`. The page's API base now defaults to its
  own origin. `WEB_DIR` points at it in the container image.
- Docker image includes `web/` and listens on `$PORT` (Cloud Run), default 8080.
- `.gcloudignore` / `.dockerignore`: allowlists, so a source upload or build context is only
  `Dockerfile`, `pyproject.toml`, `src/` and `web/` — never `.env` or `backups/`.

## [3.1.0] - 2026-10-03

### Removed — stale copy of the historical session JSON

- `output_training_logs_json/BODYBUILDING TRANSFORMATION SYSTEM/` — an older generation of the
  121 historical sessions with wrong values (e.g. RPE null and 0 kg where the current copy has
  RPE 8 and 30 kg). `eval_arms.py` globbed it alongside the current
  `bodybuilding_transformation_system/` copy as its answer key, and `test_models.py`'s
  round-trip tests read only the stale one; they now read the current copy.

### Changed — historical sessions corrected by hand (data, not code)

- Prod and `output_training_logs_json/bodybuilding_transformation_system/`: 77 working sets'
  missing quality, RPE or notes restored, 88 lost warmup sets added (non-standard headings and
  warmups written as prose), 2 working sets typed under Warmup Notes added. Every change is
  logged in `historical-review/batch1.md` / `batch2.md` with its source line.

### Added — Phase 5b Step 7, repeat a past session

- `POST /sessions/{session_id}/repeat` starts a new pending extraction from a stored session,
  with no LLM call, and returns the same ids as `POST /inputs`; the card is then edited and
  confirmed as usual. Exercises, goals, cues, warmup sets and each set's weight and reps carry
  over; RPE, quality, failure technique, rest, heart rate, duration and every note don't. The
  date is today and flagged uncertain. Works for imported historical sessions too.
- `ingest/repeat.py`. The raw input is `source_kind = 'repeat'`, `source_file` = the source
  session id, content one line naming the source, start time and raw input id (keeps each
  repeat's content-derived `session_id` unique). Extraction `model = 'none'`,
  `prompt_version = 'repeat'`.
- Schema: `raw_inputs_source_kind_check` allows `'repeat'`; `schema.sql` re-states it
  idempotently for existing databases. Applied to prod 2026-10-03 with approval.
- `GET /sessions` gains `exercises` (names in order) per session and `limit`; ties on date
  now order newest-created first.
- UI: "Or repeat a past session" under Extract lists the 15 newest sessions. During a repeat,
  the source session's notes show as a read-only "Last time" line per exercise, matched by
  name, and for the session.

### Fixed — a second app startup in one process reused a closed connection pool

- The API's shutdown closed its pool but kept it, so a later startup in the same process (a
  second test client) handed out connections from the closed pool. It now forgets the pool on
  shutdown. A single running server never hit this.

### Added — Phase 5b Step 6, which fields get corrected most

- `scripts/correction_stats.py` (read-only) and `traininglogs/analytics/corrections.py`: counts
  confirmed extractions' corrections by field pattern and source (`manual` / `ai`; records
  from before `source` existed count as `ai`), plus added/removed lines by op. A reps edit
  counts once as `reps`, not as its two extract fields.

### Fixed — AI corrections weren't counted in `llm_calls`

- `POST /extractions/{id}/correct` now records its model call in `llm_calls` (step
  `edit_extraction`), tied to the extraction's raw input, whether the correction succeeds or
  fails. Before, only extraction was logged, so the database total understated real spend.
  Corrections made before this fix are not recoverable from the database; the Anthropic
  Console has them.

### Added — Phase 5b Step 4, add and remove sets, warmup sets and exercises

- `/edit` also takes one `op` instead of `edits`: `add_set` / `add_warmup_set` (on an exercise:
  append; on a set of that kind: insert after it), `add_exercise` (on `""`: append; on an
  exercise: insert after it), `remove` (a set, warmup set, exercise, or warmup/cooldown
  movement). Exactly one of `edits` or `op` per call.
- A new set copies weight and reps from its neighbour; RPE, quality, notes and failure
  technique start empty. A new exercise is named "New exercise".
- The changed list is renumbered 1..n, and `uncertain_fields` shift with the positions
  (entries under a removed line are dropped).
- The reply gains `created_path`; the correction record gains `op` and `path`.
- UI: `+ Set` / `+ Warmup set` under each exercise, `+ Exercise` at the end of the card,
  add-after and `Remove` (asks once more inline) in each line's form. A new line opens straight
  into its form.

### Added — Phase 5b Step 3, tap a card line to edit it

- Tapping a line on the confirm card (session header, exercise name or notes, set, warmup set,
  warmup/cooldown movement) opens an inline form with every editable field for that line,
  filled in, the tapped value focused. Save sends only the changed fields to `/edit`; Enter
  saves, Escape cancels, a rejected value keeps the form open with the server's message.
  Empty values can be filled in (a missing RPE), which tapping single values couldn't do.
- Fields the model flagged as uncertain are outlined in the form.
- `/edit` and `/correct` replies share one handler; manual edits show in the corrections log
  as "Edited".

### Added — Phase 5b Step 2, edit a card value without an AI call

- `POST /extractions/{id}/edit` takes `{extract?, edits: [{path, field, value}]}` — the card
  element's `path`, the card's own field name, the new value — applies it with no LLM call, and
  replies in the same shape as `/correct` (`extract`, `card`, `correction`). Stateless and
  round-tripped the same way. An invalid value (RPE 85, unreadable reps, a field that isn't
  editable) is a 400 whose detail names the field.
- `agent/card_edits.py`: `EDITABLE_FIELDS`, the allowlist mapping each card field to its extract
  field per kind of card element. Reps are typed as written (`8`, `8+1`, `L8/R7`) and read by
  `agent/reps.py`. An empty string clears a value. Failure techniques and goals are not
  editable this way yet; a typed correction still handles them.
- A field edited on the card is dropped from `uncertain_fields`.
- Correction records gain `source`: `"manual"` from `/edit`, `"ai"` from `/correct`. Records
  stored before this have no `source`.

### Added — Phase 5b Step 1, card elements carry their extract path

- The validation card's session header, exercise headers, set rows, warmup rows and
  warmup/cooldown movement rows each gain `path`: where that element lives in the extract, by
  list position (`exercises.1.sets.0`; `""` for the session header). Returned by
  `GET /extractions/{id}` and `/correct`. Groundwork for editing a value directly without an
  AI call. `None` on rows built by hand (the terminal renderer's tests).

### Fixed — keys not scoped to a workspace were rejected

- `AnthropicProvider` sends the `anthropic-workspace-id` header when `ANTHROPIC_WORKSPACE_ID` is
  set. Keys not scoped to a workspace (`sk-ant-usr…`) are rejected by the API without it;
  workspace-scoped keys (`sk-ant-api…`) need nothing and are unaffected. Documented in
  `.env.example`.

### Added — Phase 5 Step 5, confirm UI polish pass (visual fidelity, dark mode, phone width)

- Dark mode via `@media (prefers-color-scheme: dark)`, palette matched to the approved mockup
  and `color-scheme` set on `:root` so native form controls (scrollbars, textarea resize handle)
  follow too. System-preference only, no manual toggle — matches the mockup, which didn't have
  one either.
- Responsive: the API base URL / API key row stacks vertically under 480px; exercise headers
  and the goal summary wrap instead of overflowing; `clamp()` on the page heading and top
  padding so the page doesn't waste space on a phone. No phone-frame chrome — that was the
  mockup's presentational device for showing four screens side by side, not something the real
  page should render.
- Unified button styling: `#extractBtn` was the only element relying on a bare `button {}`
  selector while every other action button used explicit `.btn-primary`/`.btn-ghost` classes —
  same visual weight by accident, not by rule. Now all primary/secondary actions share one
  definition; the composer's circular send button keeps its own distinct (intentionally
  different) shape.
- Added `:focus-visible` outlines (inputs, both button classes, the raw-JSON `<summary>`) —
  present in the mockup's own CSS but not yet carried over.
- Small wordmark treatment on the page heading (`training` + red `logs`), matching
  `docs/index.html`'s branding instead of a plain generic title.
- **Verified with zero API calls**, per explicit instruction not to spend money testing a pure
  CSS/layout change: a Puppeteer harness intercepts `fetch` at the network level (`page.
  setRequestInterception`) and returns canned responses for `/inputs`, `GET /extractions/{id}`,
  `/correct`, and a deliberately-mocked `409` on `/confirm` — driving the real click-through UI
  exactly as a user would, with no backend running at all. Checked across light/dark ×
  desktop/390px-phone (4 combinations): card rendering, a correction, and the 409 error state
  all render correctly with no console errors, no horizontal overflow, and no broken wrapping.
  A real end-to-end pass (actual API, actual money) is left for manual verification.

### Added — Phase 5 Step 4, confirm UI's confirm + error states

- "Looks good — Confirm" button wired to `POST /extractions/{id}/confirm`, sending the current
  `extract` and every correction accumulated across Step 3's calls (`{at, instruction, edits}`
  each) as `corrections`. On success, shows a confirmed screen with the real `session_id` and a
  "Log another" button that resets the whole page back to a blank capture.
- The three real failures the API returns are now surfaced as actual UI states instead of
  silently failing or dumping to the console:
  - **409** (`/confirm`, session_id collision) — the server's own message (which already names
    the likely cause: date is wrong, or this exact content was already confirmed) plus a
    pointer to use the still-visible correction box and retry. Card and composer are left in
    place on any confirm failure, not cleared — the person can fix and re-confirm without
    starting over.
  - **502** (`/inputs`, LLM extraction failure) — fixed a real bug from Step 1: `capture()`
    returns HTTP 502 with a valid body (`{raw_input_id, error}`) when extraction fails, but the
    original code checked `response.ok` *before* looking at the body, so that branch never ran
    and the useful detail (raw_input_id, actual error) was lost behind a generic "POST /inputs
    failed (502)." Now checks for `raw_input_id` in the body first, regardless of HTTP status.
  - **400** (`/correct`, bad correction patch) — already surfaced via `result.body.detail`
    since Step 3; wording now distinguishes "couldn't apply that correction" (400) from "the
    correction service failed" (502) rather than one generic message for both.
- Verified live against `TEST_DATABASE_URL`: a full extract → correct → confirm round trip
  (real session written, real `session_id` returned), and a deliberate 409 by confirming
  identical content twice — the error box showed the real server message and the page stayed
  usable, not blank or console-only. Full suite 652 passing, 0 skipped (verified stable across
  two consecutive runs — an early failure in this session was test-DB pollution from live
  testing against the shared `TEST_DATABASE_URL`, self-cleaned by `test_ingest.py`'s own
  per-test truncation, not a regression).

### Added — Phase 5 Step 3, confirm UI's correction loop

- Composer (`web/index.html`/`app.js`) wired to `POST /extractions/{id}/correct`, round-tripping
  `extract` between calls the way the endpoint's own statelessness was designed for — the client
  holds `currentExtract` (the previous response's `extract`, or `null` before the first
  correction, meaning "use the extraction's own stored reading") and sends it back on every
  call; the server holds nothing.
- Each correction re-renders the card from the response's own `card` (identical shape to
  `GET /extractions/{id}`, so `renderCard()` from Step 2 needed no changes) and appends a log
  row summarizing the applied edits (`path → value`, comma-joined for multi-field corrections).
- Verified live against `TEST_DATABASE_URL` with two sequential corrections on the same
  extraction (an RPE fix, then a weight fix across three sets): both persisted correctly after
  the second call, confirming the round-trip carries state forward rather than resetting it —
  the specific risk the roadmap flagged this step for.

### Fixed — exercise chunking could only ever locate the first of several exercises packed onto one line

- `_locate_anchor_lines`/`_chunk_exercises` (`agent/extraction.py`) isolated each exercise's
  text by finding its anchor **line** and searching strictly forward from the *next* line for
  the following exercise's anchor. A short, casual capture with no line breaks at all —
  `"Push day. Bench press 60kg for 8. Incline db press 22kg for 10."`, exactly the shape of
  input the Phase 5 confirm UI's own testing produced — has only one line, so the second
  exercise's anchor could never be found there, regardless of how much text there was. Found
  live-testing the confirm UI: `warnings` showed "Exercise 2: could not isolate its text — used
  the full document instead" on ordinary two-exercise input.
- Rewrote `_locate_anchor_lines` → `_locate_anchors`, matching on **character offset** into the
  whole document instead of line number, searching forward from the end of the previous match
  rather than the next line. This is what lets two exercises share one physical line — the
  first chunk now ends and the second begins exactly at the second anchor's own offset, rather
  than requiring each to own a line no one else can touch.
- Anchor matching now runs through a new position-preserving normalizer
  (`_normalize_for_anchor_matching`) tolerant of the same drift `_comparable()` already handles
  elsewhere in this file — curly quotes, em/en dashes, non-breaking spaces — a model asked to
  copy an anchor "verbatim" can still silently retype these even when told not to, which
  previously failed the match outright. Deliberately narrower than `_comparable()` (no NFKC, no
  whitespace collapsing): both of those can change a string's length, which would break the
  character-offset positions this function returns.
- `_chunk_exercises` now computes chunk boundaries in the order anchors were actually **found**
  in the text, not the order the model **labeled** them (`position`). Nothing enforces that a
  model's declared position numbers match its own list order; sorting boundaries by the label
  instead of the offset could pair one exercise's start with a different, wrongly-matched
  exercise's end, slicing into a neighbor's content instead of stopping at it. Not yet observed
  in practice, but reachable and now structurally prevented (a chunk's content is always exactly
  one anchor to the next, by construction) rather than merely guarded against.
- Verified live against `TEST_DATABASE_URL`: the exact two-exercise-one-line input that
  previously produced the warning now extracts both exercises cleanly, zero warnings. 13 new/
  rewritten unit tests in `test_agent_chunking.py`, all pure functions, no LLM calls. Full suite
  652 passing, 0 skipped.
- **Not yet run through `scripts/eval_arms.py`** — deliberately deferred (this is deterministic
  Python, not a prompt change, but the date fix above already re-keyed the shell-call cache, so
  a verification run costs the usual ~$0.45 either way). Do this before the branch reaches
  `main`.

### Fixed — a missing date was silently invented instead of defaulted and flagged

- `date` is a required field on `TrainingLogLLMExtract`, so when the input text had no date at
  all (only reachable in practice through the web capture path — every existing `.md` fixture
  carries a `**Date:**` line), the model filled it with a plausible-looking guess and never
  marked it `uncertain_fields`, even though that mechanism exists for exactly this. Found while
  testing Phase 5's confirm UI with undated pasted text.
- `SHELL_SYSTEM_PROMPT` (`agent/prompts.py`) now tells the model to flag `date` uncertain
  whenever the text doesn't state one, instead of guessing silently.
- `ingest.extract()` backfills a flagged `date` with the raw input's own `captured_at`
  (already stored, Phase 2) rather than trusting the model's placeholder — deterministic, and a
  real fact instead of another guess. Still left flagged: "captured today" isn't the same claim
  as "the workout happened today" (logging yesterday's session needs to stay correctable).
- `web/app.js`'s card renderer now shows a flag for any session-header-level uncertain field
  (`date`, but also `focus`/`program`/`phase`/`week`/`duration_minutes` if the model ever flags
  those) — Step 2 had only wired flags for per-set rows, not the header.

### Added — Phase 5 Step 2, confirm UI renders the card

- `renderCard()` in `web/app.js` turns the `GET /extractions/{id}` response into the review
  screen from the approved mockup: session header, warnings banner, session- and exercise-level
  warmup/cooldown blocks, per-set rows with weight/reps/RPE/quality/failure-technique, and an
  "AI inferred" flag on any row `uncertain_fields` names. Built directly against
  `UserValidationCard`'s real shape (`agent/validation_card_data.py`), not the mockup's
  fictional fields — the mockup's exercise-header "tag" (e.g. "barbell") doesn't exist on the
  card, so exercise headers show a `Goal: …` summary instead. Desktop-width, light theme only;
  phone frame and dark mode are Step 5. Raw JSON still available behind a collapsed `<details>`.

### Added — Phase 5 Step 1, confirm UI skeleton

- `web/` — new surface, plain HTML/JS, no build step (matches `docs/`'s own approach). A
  textarea and "Extract" button wired to `POST /inputs` then `GET /extractions/{id}`, rendering
  the raw card JSON. Proves the round-trip before the card gets a real layout (Step 2). API
  base URL and `X-Api-Key` are entered in the page and kept in `localStorage`; no styling pass
  yet, that's Step 5.
- `web/README.md` — how to run the API against `TEST_DATABASE_URL` and serve `web/` locally for
  development.

## [3.0.0] - 2026-08-10

### Added — Phase 4, write API — complete (POST /inputs, GET /extractions/{id}, POST .../confirm, POST .../correct)

- `POST /inputs` — `ingest.capture()` then `ingest.extract()` over HTTP, the first real
  caller of `ingest/` from `api/app.py`. Returns `{raw_input_id, extraction_id}` (201) on
  success. `capture()` commits before extraction is attempted, so a failed extraction (502)
  still returns `raw_input_id` — the text isn't lost, and the caller can retry extraction
  against the same raw input (`extract()` is idempotent) instead of resubmitting.
- `GET /extractions/{id}` — the same confirmation card the CLI's confirm loop renders to a
  terminal, as JSON. `ValidationCardBuilder` was already DB-free and shared; this adds a
  serializer (`fastapi.encoders.jsonable_encoder`, which handles the card's dataclass tree
  including its `frozenset` fields) in place of `TerminalRenderer`.
- `POST /extractions/{id}/confirm` — `ingest.confirm()` over HTTP. Accepts an optional
  `{extract, corrections}` body so it composes with whatever `/correct` ends up needing later;
  omitted, the extraction's own stored reading is confirmed as-is. The `SystemExit` `confirm()`
  raises on a `session_id` collision (fine for a CLI process to exit on, wrong for a request)
  is caught here and returned as `409`.
- `POST /extractions/{id}/correct` — applies one correction and hands back the result.
  Deliberately, fully stateless, like every other endpoint here: the server holds nothing
  between calls. The client sends `{extract, instruction}` (`extract` is the previous
  response's own `extract`, or omitted on the first correction to use the extraction's stored
  reading), and gets back `{extract, card, correction}` — `extract` to round-trip into the next
  `/correct` or into `/confirm`, `card` to render, `correction` (`{at, instruction, edits}`) to
  accumulate into the list `/confirm` eventually takes. `PatchError` (an edit names a field
  path that doesn't resolve) returns `400`; an LLM failure returns `502`.
- CORS `allow_methods` extended from `["GET"]` to `["GET", "POST"]`.
- Fixed a real connection-pool bug surfaced while adding these: `_db()`'s dependency handed
  connections back to the pool without rolling back, so a request that never explicitly
  committed (every existing `GET` endpoint; the early "already exists" return inside
  `insert_session()`) left the connection mid-transaction for the *next*, unrelated request to
  inherit — which would then see that leftover transaction's uncommitted writes as its own,
  invisible to every other connection. `_db()` now rolls back unconditionally before returning
  a connection to the pool (a no-op when everything was already committed).

### Changed — session_id is derived from content, not file path

- `compute_session_id()` now hashes the session's (whitespace-normalized) text instead of a
  file path relative to `inputs/`. Motivation: Phase 4's write API accepts content with no
  file behind it at all, so path-based identity had no answer for that case. Chose to unify
  onto one identity scheme everywhere rather than run two (path-based for the CLI,
  content-based for the API) — the same input now gets the same `session_id` regardless of
  how it arrives (file, pasted text, eventually a photo transcript), including across
  `--parser rules`, `--parser ai`, and the new `POST /inputs`.
- **Real, deliberate trade, not a side effect:** editing a file's content and resubmitting no
  longer updates the same session in place — it produces a new `session_id`, since the content
  changed. The previous scheme's "fix a typo, rerun, same session" behavior is gone; what's
  gained is that identical content submitted twice, from any source, is now caught by the
  existing session_id-collision check instead of silently becoming a duplicate session.
- `session_id` was never guaranteed stable across code changes to begin with — it already
  changed once before (`.claude/regen-historical.md`), which is why that guide already says to
  compare regen output on `date`, not `session_id`. This is the same category of change.
- `build_session_from_extract()` and `ingest.confirm()` both take `content`/fetch it from the
  raw input now; `md_path` is optional on both, used only to enrich `program`/`phase`/`week`
  from the file's directory position when one exists. No change to existing `sessions` rows —
  this only affects sessions processed going forward.

### Fixed — AI path silently dropped rep_quality_assessment and failure_technique

- `SetExtract` (the schema the model actually fills in) never had fields for these two,
  unlike the other classification fields it deliberately omits — this one had no
  "not asked for, and why" note, because it wasn't a decision. Every session logged
  through `--parser ai` since the split pipeline shipped has `rep_quality_assessment`
  and `failure_technique` unset regardless of what the source text says.
- Added `rep_quality_assessment` and `failure_technique_raw` to `SetExtract`.
  `failure_technique_raw` accepts either the compact notation the rules parser already
  understands (`failure:myo(3,3,3)`) or a plain description — the compact form is
  parsed by reusing `parser/parse.py`'s `_parse_failure`/`_parse_quality` (the exact
  code the rules path already uses, not a reimplementation); a plain description that
  doesn't match is never dropped, it's kept visible in the set's `notes` with a
  warning, same rule the prompt already gives the model for anything else it can't
  map to a field. A technique noted at RPE other than 10 is also dropped with a
  warning rather than raising (`WorkingSet` requires RPE 10 for a failure technique).
- Fixed the worker prompt's own worked example, which was teaching the model to fold
  quality words into `notes` — that's what the schema previously required, but it
  actively worked against the new field once added. Added a second example
  demonstrating the failure-technique notation.
- Verified against 3 real sessions (push/pull/legs, chosen for length and technique
  variety) run through the real AI pipeline against a reset `db_regen`, compared
  field-by-field against the existing rules-parser JSON: every difference found was
  the *old* data being wrong or incomplete (a quality word on the same line as a
  failure notation, an `RPE` token in an order the old regex didn't expect) — zero
  cases of the new extraction being wrong. `failure_technique` matched exactly
  wherever it appeared, including both `MyoReps` and `LLP` shapes.
- 9 new unit tests (`tests/test_agent_source_lines.py`).

### Fixed — GroqProvider had no call instrumentation

- `AnthropicProvider.calls` was added below (D4/D6/D7) without the matching change to
  `GroqProvider` — a real gap, since `ExtractionProvider` is a Protocol precisely so any
  provider can be swapped in by parameter, and `ingest.extract()` / `_process_ai_file()` both
  already accept either one. `GroqProvider` now carries `self.calls` too, in the identical
  shape, via a new shared `_record_call()` helper both providers call from their own `finally`
  block (Groq's own token-usage fields are named differently — `prompt_tokens`/
  `completion_tokens` vs Anthropic's `input_tokens`/`output_tokens` — translated to the same
  two ints before the shared helper ever sees them). `PRICING` gained an entry for Groq's
  default model at `(0.0, 0.0)`. Verified against a real (free-tier) Groq call, not just
  mocked: `llm_calls` now gets three real rows — `split_exercises`, `extract_session_shell`,
  `extract_exercise` — with real token counts and timings, where it previously stayed empty
  for any Groq-driven run.

### Added — cost and call visibility (Phase 3, step 3: D4, D6, D7)

- `llm_calls` table — one row per extraction step (segment/shell/worker/correction), not per
  raw HTTP attempt: `raw_input_id, step, model, attempts, input_tokens, output_tokens,
  cost_usd, ms, cached, failed, raw_payload`. Makes cost a SQL query instead of something read
  out of console output (D4). `cached` is always `false` today — prompt caching was measured
  and dropped (B9) — the column is reserved rather than invented later.
- `AnthropicProvider.calls` — accumulates one record per `extract()` call, appended in
  `finally` whether the call succeeds or exhausts its retries. `raw_payload` holds the last
  tool-call payload the model returned even when `validate()` rejected every attempt, so a
  validation failure no longer also costs the response that triggered it (D6). Previously
  nothing about a failed call's actual output survived past the raised exception.
- Two distinct `[llm]` log lines replace one conflated code path: "call succeeded, no tool
  call in response" and "call succeeded, result not usable" (D7). The `mono` truncation
  incident was the API answering successfully with an unusable result, not an outage — before
  this, both looked identical in the retry loop.
- `ingest/extract.py` drains `provider.calls` into `llm_calls` after `assemble()` returns *or
  raises* — a run that fails partway through still spent money on the calls it made, and that
  cost does not disappear with the exception. `cli/log.py`'s `_process_ai_file` separately
  drains whatever the confirm loop's corrections added afterward, since those are calls made
  after `extract()` has already returned and persisted its own batch.
- Two `raw_input_id`-tagged `[ingest]` log lines bracket `assemble()` in `extract()`. **D5 is
  scoped to this, not threaded through every provider call**: `raw_input_id` is not passed into
  `ExtractionProvider.extract()` itself, which would have meant changing the protocol and every
  call site (including test doubles across half the test suite) for one logging field. The
  durable, queryable form of "one id shows a session's whole life" is `llm_calls` and
  `raw_inputs`/`extractions`, both already keyed by it — a SQL `WHERE raw_input_id = ...`
  answers the question the roadmap motivation actually asks for.

### Added — ingest/ module (Phase 3, step 1)

- `ingest/capture.py`, `ingest/extract.py`, `ingest/confirm.py` — three single-job functions,
  each reading its input from the database and saving its own output before returning:
  `capture(text) -> raw_input_id`, `extract(raw_input_id) -> extraction_id`,
  `confirm(extraction_id, final_extract) -> session`. Restartable by construction — nothing is
  passed in memory between them.
- `extract()` is idempotent (D3): a `raw_input_id` with an existing pending or confirmed
  extraction returns that id instead of paying for a second model call. A rejected extraction
  does not count, since rejecting one is how a person asks for another attempt.
- `db.insert.confirm_extraction()` — marks an extraction confirmed and records its corrections
  in one statement, so `status` and `confirmed_at` cannot disagree (same reasoning as
  `insert_extraction`'s existing `CASE WHEN`).

### Changed — cli/log.py drives ingest/ directly (Phase 3, step 2)

- `LLMOrchestrator.run()` split into `confirm_loop(extract)` (new — the render/ask/apply-
  correction loop, no model call to produce the initial extract) and `run(text)` (unchanged
  behavior: `assemble()` then `confirm_loop()`). This is what lets extraction happen without
  ever blocking on a terminal: `ingest.extract()` calls `assemble()` directly, and the
  interactive loop that used to be bundled into the same call now lives only where a human is
  actually present.
- `cli/log.py`'s `--parser ai` path now calls `ingest.capture` → `ingest.extract` →
  `LLMOrchestrator.confirm_loop` → `ingest.confirm`, instead of one function that did all four
  steps inline. `processor.write_session_json()` is new, factored out of what used to be two
  copies of the same JSON-write block.
- **Removed** `processor.process_md_file_with_ai()` — superseded by the above; its logic now
  lives in `ingest/` and `cli/log.py`'s `_process_ai_file`. `cli/validate.py` is unaffected (it
  never touched the database and still calls `LLMOrchestrator.run()` directly).

### Removed — the monolithic extraction path (Phase 2, step 5)

- `SYSTEM_PROMPT` (7,295 chars), `MOVEMENT_SKILL_CONVENTIONS` (2,692 chars),
  `extraction.parse()`, `TOOL_NAME`/`TOOL_DESCRIPTION`, `LLMOrchestrator`'s
  `use_monolithic_parser` argument, the `TRAININGLOGS_USE_MONOLITHIC_PARSER` environment
  variable, and the `mono` arm of `scripts/eval_arms.py`.

  Its last caller outside itself was the correction path, which moved to patches in step 4.
  Keeping it runnable was to de-confound a split-vs-mono verdict that is no longer in question:
  mono's output scales with session size and hit the `max_tokens` ceiling on 2 of 6 files, it
  gives no per-exercise failure isolation, and it cannot survive photo or speech input.

- **Discovered while deleting it, and worth stating separately: six of the eight domain
  conventions in `SYSTEM_PROMPT` are absent from the three live prompts** — juggling and
  skill-run counts, reaction-time drills, static holds, clean-vs-failed attempt mapping, the
  rule that ordinary reps with varying quality stay whole, and one exercise-level RPE applying
  to the last set only. They stopped being applied when the split path became the default, not
  when the constant was deleted; deleting it made an existing gap visible. All of it is
  preserved verbatim in `docs/extraction-conventions.md`, with a table of what is and is not
  covered. Migrating them is an open decision with a cost: changing a live prompt changes
  `PROMPT_VERSION`, invalidates the eval cache, and needs a paid run to confirm no regression.

  The schema is unaffected and still supports every shape involved —
  `TestAdhocMovementSkillsSchemaFit` tests the models rather than the prompt text and continues
  to pass. Tests that asserted on `SYSTEM_PROMPT`'s prose were removed with the prompt; tests
  that exercised `parse()` were removed with the function.

### Changed — corrections are edits, not rewrites (Phase 2, step 4)

- **C6.** `LLMExtractValidator.apply_correction` asks the model for a list of
  `{path, value}` edits and applies them in Python, instead of sending the whole extract and
  asking for the whole extract back. Fields the correction does not name **cannot** change —
  previously the only guarantee was the sentence "keep all unchanged fields exactly as they are"
  in a prompt, and nothing would have detected a quietly altered set.

  Measured on a real 10-exercise session: the old shape needed **~5,410 output tokens against
  `max_tokens=4096`**, so it could not have returned a correction for a session that size, only
  a truncated one. Cost is secondary and the roadmap's 40x estimate was wrong — it is **5.9x**
  ($0.0368 → $0.0062), because the extract is still sent as context so input barely moves.
  Output drops 90x, and output is priced at 5x input.

  New: `agent/patch.py` (`FieldEdit`, `ExtractPatch`, `apply_edits`, `PatchError`) and
  `CORRECTION_SYSTEM_PROMPT`. A path that does not resolve raises rather than silently doing
  nothing — a typo'd path that changes nothing is worse than a failure, because the person
  believes their correction landed.

  The correction path no longer uses `SYSTEM_PROMPT`/`extract_workout`, which was its last
  caller outside the deprecated monolithic parser.

- **C7.** `extractions.corrections` (JSONB, appended to, never rewritten) and
  `extractions.extract` now holds **the model's own reading**, not the corrected one. Three facts
  stay separable: what the model said, what the person changed, what was stored. Byproduct:
  "which fields do I correct most often?" is a SQL query over `corrections`, which is a
  prompt-improvement backlog generated from real use rather than guesswork.
  `LLMOrchestrator` exposes `original_extract` and `corrections` after `run()`; it does no
  database work itself.

### Added — the ingest path writes all three layers (Phase 2, step 2)

- `sessions.extraction_id` — nullable FK to `extractions`, so a stored session can be traced
  back to the reading that produced it and the text that reading came from. Added by
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, because `CREATE TABLE IF NOT EXISTS` does nothing
  to a table that already exists and would have skipped the column silently.
- `processor.process_md_file_with_ai()` — the AI parser path, moved out of a nested function
  inside the CLI. It captures the raw input, runs the confirmation loop, stores the extraction
  with its model/prompt/uncertain_fields/warnings, then inserts the session linked to both.
  `orchestrator` and `model` are injectable so it can be tested without an API call.
- `processor.relative_source_file()` — one helper, used by both parser paths.
- `insert_session()` takes `source_file` and `extraction_id`.

### Fixed

- **C8 — `source_file` was never set on the AI path.** The rules path set it with an `UPDATE`
  after inserting; the AI path did not, so every AI-parsed session in the database has no link
  to the text it came from. Both paths now pass it to `insert_session`, which writes it with the
  row — two callers, one of which forgot, is the failure mode a parameter removes. The
  post-insert `UPDATE` is gone. Existing rows are not backfilled by this change.
- `extractions.confirmed_at` is derived from `status` in the insert rather than set separately.
  Two fields that must agree, set independently, eventually disagree.

Audited and unchanged: an extraction that failed for one exercise still stores a placeholder
exercise with a sentinel in `notes`, and `insert_session` still accepts it. That is a confirmed
choice made by the person at the card, not a silent write — but finding such sessions used to
mean a `LIKE` against prose. It is now `WHERE warnings <> '{}'` on the extraction.

### Added — capture and interpretation layers (Phase 2, step 1)

- `raw_inputs` table: what the person actually produced, never edited. `id`, `content`,
  `source_kind` (`markdown`|`photo`|`speech`, CHECK-constrained), `source_file` (null for
  spoken or pasted input), `checksum` (sha256 of the content), `captured_at`. Identical text
  is deliberately **not** deduplicated — repeating a session is a real thing a person does, and
  collapsing two captures into one would make them indistinguishable. The checksum is indexed
  so finding duplicates is a query; deciding what to do about them belongs to the ingest path.
- `extractions` table: one attempt at reading a raw input. `raw_input_id` FK (cascading),
  `model`, `prompt_version`, `extract` (JSONB), `uncertain_fields`, `warnings`, `status`
  (`pending`|`confirmed`|`rejected`, CHECK-constrained), `created_at`, `confirmed_at`.
  Many-to-one by design: re-reading the same text with a better model or a fixed prompt must not
  require the person to write anything twice.
- `insert_raw_input`, `insert_extraction`, `content_checksum` in `db/insert.py`; `get_raw_input`,
  `find_raw_inputs_by_checksum`, `get_extraction`, `get_extractions_for_raw_input` in
  `db/fetch.py`.
- `prompts.PROMPT_VERSION` — a 12-character hash of the three live prompts, recomputed on
  import. Derived rather than declared, because a hand-maintained version constant is only
  correct while someone remembers to bump it.

Nothing writes to these tables yet — this step is purely additive, so no existing behaviour
changes. `schema.sql` uses `CREATE TABLE IF NOT EXISTS` throughout, so applying it to an
existing database adds the two tables and touches nothing else.

Validation rules in effect: `raw_inputs.source_kind` must be one of `markdown`/`photo`/`speech`;
`extractions.status` must be one of `pending`/`confirmed`/`rejected`; an extraction cannot
reference a raw input that does not exist, and is deleted with it.

### Fixed — extraction reliability (2026-08-06)

A measurement run scored 215/277 on core fields, down from 98.8%. The cause was not extraction
quality: on every exercise the model actually returned it was **147/147**. Five worker calls
returned `{"number": 1}` — no name, no sets — and each became an exercise-shaped hole.

- **Validation now runs inside the provider's retry loop.** `ExtractionProvider.extract()` takes
  a `validate` callback and re-asks when the payload fails it. Previously validation lived in the
  callers (`parse`, `segment`, `extract_shell`, `extract_exercise`), one layer above the loop, so
  a tool call that parsed as JSON but didn't satisfy its model got none of its three attempts.
  The reask replays the failed `tool_use` and answers it with a `tool_result` carrying
  `is_error`, so the model sees what it sent and why it was wrong. Groq uses the equivalent
  OpenAI `tool` role shape.
- **`strict: true` on Anthropic tool definitions.** Grammar-constrained sampling makes a call
  that omits a required field impossible to generate, rather than something to recover from.
  `strict_schema()` adds the required `additionalProperties: false`; a test pins that the live
  schemas stay inside the supported subset, since the API answers an unsupported schema with a
  400 rather than degrading quietly.
- **An extract with no working sets and no warmup sets is rejected.** It was schema-valid and
  invisible: `check_sources_are_real()` and `check_sets_are_numbered_and_sourced()` both iterate
  over the sets that came back, so zero sets produced zero findings. One token's difference from
  the observed failure would have written a clean-looking session with every set silently
  missing. It now takes the retry path, and only becomes a flagged placeholder if every attempt
  comes back empty.
- **Removed `ExerciseExtract.number`.** The splitter already knows each exercise's position and
  `assemble()` overwrote whatever the worker reported, so the field asked the model for
  information that was discarded — and it was the one field the failing calls did fill.
  `to_exercise(number)` now takes the position from the caller.
- **A worker handed an isolated chunk is no longer told to find "exercise number N".** That
  instruction only makes sense in the full-document fallback, where it is still used.
- **Removed the exercise-count check in `audit()`.** `assemble()` appends exactly one exercise
  per split entry, extracted or placeholder, so the counts were equal by construction and the
  check could never fire — the same defect as the kg-token check removed before it.

Validation rules in effect: `ExerciseExtract` requires a non-empty `name` and at least one
working or warmup set; `SetExtract` requires `source_line` and a positive `number`.

### Added (v3.0.0 data model — Steps 1–5 complete, Step 6 (cloud validation) + Step 7 (JSON comparison) remaining)

- `WorkingSet`: flat model replacing `StrengthSet`/`ActivitySet`/`AnySet` discriminated union.
  All measurement fields optional (`weight_kg`, `rep_count`, `unilateral_rep_count`,
  `duration_seconds`, `distance_meters`, `heart_rate_bpm`). Mixed sets (e.g. timed strength work
  with both `weight_kg` and `duration_seconds`) are valid.
- `SessionWarmup`, `SessionCooldown`: new lightweight models (`number`, `name`, `reps`,
  `duration_seconds`, `notes`) for warmup and cooldown phases. Stored in their own
  `warmups`/`cooldowns` tables (not mixed into `exercises`).
- `TrainingSession.warmup`, `TrainingSession.cooldown`: `Optional[List[SessionWarmup/Cooldown]]`.
  Sequential numbering validated per-group independently (warmup, exercises, cooldown each start at 1).
- `Exercise.tags: Optional[List[str]]` — NASM OPT / NSCA-based vocabulary:
  `absolute_strength`, `muscle_growth`, `muscle_endurance`, `explosive_power`,
  `core_stabilization`, `balance_control`, `passive_flexibility`, `active_mobility`,
  `cardiorespiratory`, `saq`, `sport_specific`.
- `Exercise.modality: Optional[str]` — free-text equipment/modality descriptor
  (e.g. `"barbell"`, `"bodyweight"`, `"cable"`).
- `Exercise.movement_pattern: Optional[List[str]]` — list to support compound patterns;
  vocabulary: `squat`, `hip_hinge`, `push`, `pull`, `lunge`, `carry`, `rotation`.
- `TrainingLogLLMExtract`: `warmup` and `cooldown` fields added; `SYSTEM_PROMPT` updated with
  NASM/NSCA tag rules and warmup/cooldown extraction guidance.
- `GroqProvider`: free Groq API alternative to Anthropic for local testing; uses JSON mode.
  Selectable via `--parser groq`.
- Movement-skill intake: `SYSTEM_PROMPT` conventions for calisthenics, gymnastics rings,
  juggling, reaction drills, shadow boxing, and kettlebell/dumbbell work — usable both
  ad-hoc (unprogrammed) and mixed into a real structured phase/week program. No model
  changes — existing fields cover every case: skill-run counts (e.g. juggling catches)
  and skill-attempt counts (e.g. muscle-up tries) map to `rep_count` (attempts that
  complete cleanly are `full`, attempts that don't are `partial` — the same distinction
  a normal working set already makes; ordinary reps with varying form quality stay
  `full` regardless — only genuine attempt/clean phrasing triggers the split); static
  holds and timed rounds map to `duration_seconds`; reaction-time drills use `rep_count`
  for attempt counts with measured times (ms) in `notes`, never in a numeric field.
  Ad-hoc sessions (no program, no phase/week) leave `program`/`phase`/`week` all unset —
  no pseudo-program name is invented. `inputs/sessions/` is the documented location for
  these (mirrors the pre-existing "standalone session" concept already covered by
  `tests/test_processor.py`); `inputs/programs/` stays reserved for real structured
  programs. A session with phase/week but no stated program name also leaves `program`
  unset rather than guessing, since it belongs to a real program whose name lives
  outside the file text (usually the directory path). Copy-pasteable templates in
  `templates/`: `adhoc-template.md` + two worked examples (`adhoc-example-home-skills.md`,
  `adhoc-example-gym-calisthenics.md`) for `inputs/sessions/`, and
  `programmed-example-calisthenics-mixed.md` showing calisthenics mixed into a real
  phase/week session using the existing gym-log format (no new template needed there).
  Exercise prompt fix bundled in: `exercises` now explicitly excludes warmup/cooldown
  movements (previously ambiguous, occasionally double-counted).
- Session-level `notes: Optional[str]` on `TrainingSession` and `TrainingLogLLMExtract`
  (+ `sessions.notes` column), for remarks that don't belong to any specific exercise or
  set (e.g. an observation made before the first exercise). `SYSTEM_PROMPT` updated with a
  general catch-all: any text that can't be mapped to a structured field is attached as a
  note at the most specific level it clearly belongs to (a named set, a named exercise or
  movement, falling back to the session-level `notes` only when nothing more specific
  applies) — never silently dropped. RPE stated once for a whole exercise (a remarks block
  after all its sets, rather than inline per set) now defaults to the *last* set only (upper
  bound if a range), flagged `uncertain_fields`, with an explicitly named set overriding the
  default — replaces the previous undefined behavior that could spread one RPE value across
  every set in the exercise. Deliberately dropped `"Movement:"` as a `focus` alias rather
  than maintaining a growing keyword-alias list — it appeared exactly once across all real
  historical inputs and is redundant with the session's own exercise list; unmapped labels
  now just fall through to the notes rule above instead of needing bespoke handling.
  `ValidationCardBuilder`/`TerminalRenderer` updated: a session-level note preview renders
  right after the session header, same truncation behavior as exercise notes.

### Fixed

- `AnthropicProvider`/`GroqProvider` now pin `temperature=0` on every extraction call.
  Neither pinned a temperature before, so identical input to `--parser groq` could produce
  materially different extractions between calls — in one investigated case, two of three
  repeated live calls on the same real session file silently dropped an exercise-level RPE
  remark entirely (no value, no note) for the last 3 of 6 exercises, while the third call
  extracted every one correctly. Ruled out token-limit truncation first (`finish_reason:
  tool_calls`, not `length`) before concluding it was sampling-temperature variance on what
  should be a deterministic extraction task.

### Removed (v3.0.0 data model)

- `StrengthSet`, `ActivitySet`, `AnySet` — replaced by flat `WorkingSet`.
- `Exercise.exercise_type` — replaced by `tags` + `modality`.
- `set_type` discriminator field — no longer emitted by the LLM or stored anywhere.

### Removed

- `traininglogs log --publish` and `cli/log.py::_publish_dashboard()` — dead code.
  It pushed a copy of the dashboard to `website/static/training-almanac/index.html`,
  a path that predates the Wave 7 website restructure and that nothing writes to
  anymore. The website now pulls `docs/index.html` directly from this repo at
  deploy time instead, so publishing a copy is unnecessary. `--publish` was a
  silent no-op before this removal. Docs (`README.md`, `CLAUDE.md`,
  `.claude/testing-guide.md`, `docs/design.html`) updated to match.

---

### Added

- `--parser ai|rules` flag on `traininglogs validate` and `traininglogs log`.
  `--parser ai` (default) runs the `LLMOrchestrator` confirmation loop before
  writing to the DB. `--parser rules` runs the existing deterministic pipeline.
- `processor.build_session_from_extract()` — converts a confirmed
  `TrainingLogLLMExtract` into a `TrainingSession`, injecting system fields
  (`session_id`, `user_id`, `user_name`, `data_model_version`,
  `data_model_type`) and path-derived program context.

- `agent/validation_card_builder.py`: `ValidationCardBuilder` — converts a
  `TrainingLogLLMExtract` into a `UserValidationCard` dataclass tree. Resolves
  `uncertain_fields` dot-paths (e.g. `"exercises.0.sets.1.rpe"`) to per-component
  `frozenset[str]` fields on `SessionHeader`, `ExerciseHeader`, `WarmupRow`, and
  `WorkingSetRow`. Formats rep strings (`"8"`, `"8+2"`, `"10L / 9R"`), failure
  technique summaries, and goal summaries.
- `agent/llm_extract_validator.py`: `LLMExtractValidator` — applies a user's
  freeform correction to a `TrainingLogLLMExtract` via the `ExtractionProvider`
  interface, then re-validates with Pydantic. Raises `LLMParserError` on permanent
  failure.
- `agent/llm_orchestrator.py`: `LLMOrchestrator` — full AI-parser flow: parse text
  → build card → render → stdin correction loop → re-render → repeat until user
  confirms → return validated `TrainingLogLLMExtract`. Injectable `input_fn` and
  `renderer` for testing.

---


### Added (pipeline evaluation, 2026-08-02)

- `scripts/eval_ab.py` — model A/B harness with an on-disk response cache keyed by the full
  request hash, a `--max-cost` abort, `--dry-run`, and per-call spend logging to `calls.jsonl`.
  No paid call is ever made twice, across runs or after a crash.
- `scripts/eval_arms.py` — pipeline-architecture comparison (`split-pf` / `split-nopf` / `mono`)
  scored automatically against the historical JSON in `output_training_logs_json/`, matched to
  each input by the `session_id` path hash. Numeric spine only; classification fields are not
  scored because they postdate that data.
- `assemble()` gained `use_parse_first` and `TRAININGLOGS_DISABLE_PARSE_FIRST` — a measurement
  escape hatch that runs the pipeline with `parse_exercise_block()` disabled. Explicitly not a
  production mode; removed together with parse-first in roadmap Phase 1.
- `roadmap.md` — single forward plan superseding `archived/plans/orchestration-refactor-plan.md`,
  `archived/plans/extraction-accuracy-plan.md`, and the Cloud Deployment Wave in `archived/plans/pre-online-plan.md`.

### Fixed

- Non-retryable API errors (billing, quota, permission) now raise `LLMParserError` immediately
  instead of consuming the full reask budget. Previously a credit-balance 400 burned three
  attempts on a guaranteed failure and buried the real cause under "failed after 3 attempts".
  Applies to both `AnthropicProvider` and `GroqProvider`.

### Removed

- `scripts/spot_check_ai_parser.py` — imported `traininglogs.agent.llm_parser`, removed in the
  split-extraction refactor; the script had been dead since.
- `scripts/validate_with_model.py` — Groq-specific comparison runner, superseded by
  `scripts/eval_arms.py`.


### Removed (parse-first, 2026-08-03)

- `parse_exercise_block()` and `src/traininglogs/agent/exercise_block.py` — the deterministic
  per-exercise block parser. Measurement showed it fired on **0 of 10 exercises in real input
  files**: it required exact-match `Warmup:` / `Sets:` / `Remarks:` header lines, while real
  logs use markdown (`### Working Sets`). It had never run in production, only against the older
  `tests/fixtures/valid/programmed_*.md` format it was validated on. The pure-AI path scores
  ~99.7% on the numeric spine across 6 real sessions with Haiku 4.5.
- `extract_exercise_labels()`, `LABELS_SYSTEM_PROMPT`, `LABELS_TOOL_NAME`/`_DESCRIPTION`, and
  the `ExerciseLabelsExtract` schema — the narrow classification-only worker path, reachable
  only when parse-first succeeded.
- `assemble()`'s `use_parse_first` parameter and `TRAININGLOGS_DISABLE_PARSE_FIRST` env var —
  the measurement escape hatch added to run this comparison. `assemble(text, provider)` again.
- `tests/test_agent_exercise_block.py`, `tests/test_agent_exercise_labels.py`, and
  `TestAssembleReproducesOriginalFailures` in `tests/test_agent_assembler.py`. **Coverage note:**
  that last class proved two of the three original extraction failures were structurally
  impossible — a guarantee that held *because* the parser supplied the numeric spine. With the
  model supplying it instead, the same tests would only assert that a scripted value came back
  unchanged, so they were deleted rather than rewritten into something weaker than they look.
  That coverage moves from unit-level structural proof to measurement: `scripts/eval_arms.py`
  scores real extractions against historical data, and `audit()` (strengthened next in roadmap
  Phase 1) is the runtime guard.
- `eval_arms.py`'s `split-pf` arm, which is no longer distinguishable from `split`.

Suite: 467 passed, 0 failed, 0 skipped (was 483; the 16 removed covered deleted code).

## [2.0.0] - 2026-05-07

### Added

- `inputs/` directory layout: `inputs/programs/<slug>/phase_N/week_N/` for program
  sessions; `inputs/sessions/` for standalone workouts not tied to a program.
- `tests/fixtures/` with three canonical fixture files: `strength_session.md`,
  `activity_session.md`, `unilateral_session.md`.
- `traininglogs validate <file>` subcommand — parses and validates a session file,
  prints a model summary, exits non-zero on failure. No DB write.
- `ActivitySet` model and `### Activity Sets` markdown header. Supports any
  combination of `duration_seconds`, `distance_meters`, `heart_rate_bpm`.
- Unilateral rep support on `StrengthSet` via `left`/`right` keywords; partial
  reps (`left 8 + 1`) map to `{full, partial}` per side.
- `Rest(BaseModel)` with `minutes` and `seconds` fields; validators reject both
  being set simultaneously.
- `AnySet` discriminated union (`StrengthSet | ActivitySet`) on `set_type`.
- `weight_unit: Literal["kg", "lbs"] = "kg"` on `TrainingSession`; lbs→kg
  conversion runs at parse time.
- `exercise_type TEXT NOT NULL DEFAULT 'strength'` on `exercises` table.
- `set_type`, `duration_seconds`, `distance_meters`, `heart_rate_bpm`,
  `left_reps_full`, `left_reps_partial`, `right_reps_full`, `right_reps_partial`,
  `rest_seconds` columns on `working_sets` table.
- `weight_unit TEXT NOT NULL DEFAULT 'kg'` on `sessions` table.
- 15 unit tests in `tests/test_parse.py` covering error paths and happy paths for
  `_parse_goal`, `_parse_warmup_set_line`, `_parse_working_set_line`, and
  `build_training_session`.
- `tests/fixtures/valid/standalone_session.md` — canonical fixture for a
  session with no program context.
- `tests/test_validate.py` — 7 tests covering `traininglogs validate` against
  valid and invalid fixtures.
- `api/schemas.py`: `SessionSummary`, `SessionDetail`, `ExerciseOut`,
  `WorkingSetOut`, `WarmupSetOut`, `ExerciseHistoryRow`.
- Supabase cloud DB as primary database. `DATABASE_URL` targets Supabase; schema
  applied and all 121 historical sessions populated.
- Fly.io deployment for the FastAPI. `Dockerfile` and `fly.toml` added; API live
  at https://traininglogs-api.fly.dev.
- Optional local Postgres mirror: CLI writes to `LOCAL_DATABASE_URL` when set and
  reachable, skips silently if not.
- `scripts/apply_schema_supabase.py` — one-shot schema migration helper for Supabase.
- `.env.example` updated to document `DATABASE_URL` (Supabase) and
  `LOCAL_DATABASE_URL` (optional local mirror).
- `inputs/programs/bodybuilding_transformation_system/program.md` — program metadata
  file consumed by the dashboard for display.

### Changed

- **Session ID scheme** — `YYYY-MM-DD_focus_N` replaced by
  `YYYY-MM-DD-<sha256[:6] of path relative to inputs/>`. Deterministic: same file
  path always produces the same ID.
- `traininglogs log` accepts a positional `<file>` or `<dir>`, or
  `--program <slug> --phase N --week N` to resolve to
  `inputs/programs/<slug>/phase_N/week_N/`. Old `--phase`/`--week` required args
  removed.
- `parse.py` now returns plain dicts shaped directly for `model_validate()`. No
  intermediate dataclass layer.
- `processor.py` pipeline: parse → inject `session_id` → lbs conversion →
  `model_validate()`. No bridge step.
- `Exercise.working_sets` renamed to `sets`. API response key `working_sets`
  renamed to `sets`.
- `Goal.rest_minutes` replaced by `rest: Optional[Rest]`.
- Module renames: `models_v2`→`models`, `insert_v2`→`insert`,
  `processor_v2`→`processor`. Script renames: `regen_v2`→`regen_historical`,
  `compare_v2`→`compare_sessions`, `import_json_to_db_v2`→`import_sessions_to_db`.
- `inputs/` replaces `input_training_logs_md/` as the working inputs directory.
  121 historical session files migrated.
- All 121 historical JSON snapshots regenerated with the new pipeline (path-based
  session IDs, `sets` key, `set_type` discriminator, `Rest` goal field).
- Dashboard visual/design refresh: six-section layout, cleaner white theme,
  Inter + JetBrains Mono typography, and program auto-discovery docs aligned with
  `scripts/build_dashboard.py` and `docs/index.html` generation flow.
- Dashboard (`scripts/build_dashboard.py`, `docs/index.html`): e1RM section dropped;
  programs now auto-discovered from `inputs/programs/`; overview layout streamlined.
- `docs/design.html`: updated to reflect Supabase primary DB, dual-write CLI behavior,
  Fly.io API deployment, and dashboard auto-discovery of programs.

### Fixed

- `_parse_working_set_line`, `_parse_warmup_set_line`, `_parse_goal`,
  `build_training_session` — silently returned `None` on malformed input; now raise
  `ValueError` with the offending content.
- `processor.py`: `Goal.rest_minutes` was not mapped to `Goal.rest` — `goal_rest_min`
  was stored as NULL for every session.
- 27 input files with invalid formats corrected: single rep count (`10 reps` instead
  of `10-12 reps`), `+` suffix on goal weights, explicit `kg` unit in warmup lines,
  bare-number warmup line.
- `fetch.py`: `get_sessions()` and `get_session()` now select all new columns;
  result key renamed `working_sets`→`sets`.
- `validate.py`: imported deleted `_to_primitive` and `is_dataclass`; replaced
  old bridge loop with the current pipeline (mirrors `process_md_file` minus
  DB/JSON steps).
- `parse.py`: `program`, `phase`, `week`, `duration` are now Optional — absent
  program context fields return `None` (standalone sessions). Hardcoded program
  name and author defaults removed.
- `processor.py`: JSON output path crashed for standalone sessions (`TypeError`
  on `None` program/phase/week). Now routes to `output_dir/sessions/` when
  program context is absent.
- `parse.py`: silent `0 x 0` fallback in `_parse_working_set_line` removed;
  now raises `ValueError` like all other malformed-line paths.
- `parse.py`: program-context trigger changed from program-presence to
  phase/week-presence — real input files have no `- Program:` line; phase and
  week are the co-dependent signals that mark a session as program-affiliated.
  Either alone is malformed and raises `ValueError`.
- `processor.py`, `validate.py`: `_derive_program_context()` added — infers
  `program`, `phase`, and `week` from the `inputs/programs/<slug>/phase_N/week_N/`
  directory structure and injects them when file metadata omits them. Program
  name in file metadata still wins if present.
- `validate.py`, `log.py`: `Path.resolve()` applied to user-supplied paths so
  session IDs are correctly path-derived (SHA256 of full relative path) rather
  than filename-only.
- `parse.py`: working set lines with unit-annotated weights (`30 kg x 6`)
  now parse correctly; unit is stripped, value stored as kg.
- `parse.py`: rep count is now optional on working set lines — failure sets
  that log weight and RPE without a rep count are valid (`57 x RPE 10 failure:llp(8)`).
- Two corrupt input lines corrected (user-approved):
  `phase_2/week_11/lower_strength`: RPE 13 → RPE 10;
  `phase_2/week_6/push_hypertrophy`: `2. 13.6` → `2. 13.6 x 12`.
- `schema.sql`: `created_at TIMESTAMPTZ DEFAULT now()` added to sessions;
  `idx_exercises_session_id` and `idx_working_sets_exercise_id` indexes added.
- `api/app.py`: `CORSMiddleware` (driven by `ALLOWED_ORIGINS` env var);
  `SimpleConnectionPool` replaces per-request connections; `apply_schema`
  removed from lifespan; Pydantic response models on all routes.
- `scripts/repopulate_db.py`: `--regen` flag uses `REGEN_DATABASE_URL`
  (port 5434 staging DB) with safety guards against cross-target accidents.
- `scripts/validate_regen.py`: strict exact-count validation plus 10-file
  spot-check (live parse vs DB) before any prod repopulate.
- `docker-compose.yml`: `db_regen` service at port 5434.
- `.claude/db-migration.md`: full regen process documented with step-by-step
  commands and the explicit prod-approval rule.
- `api/app.py`: `API_KEY` was read at module import time — test env overrides applied
  after import had no effect. Now read at call time.
- CI workflow: `docs/**` path was missing from push/PR triggers — edits to
  `docs/design.html` did not trigger CI runs.

### Removed

- `models_dataclass.py` — legacy parallel dataclass layer.
- Old `--phase`/`--week` as standalone required args (replaced by the
  `--program/--phase/--week` combination or a positional target).
- `docs/architecture.md` — content subsumed by `docs/design.html`.
- `apply_schema` removed from `traininglogs log` — schema is never auto-applied at
  runtime; migrations are explicit. Dead `apply_schema` import removed from
  `processor.py` (was imported but never called).
- `load_dotenv()` removed from `processor.py` top level — library modules must not
  have side effects. Moved to the correct call site in `log.py`, now runs before
  the `DATABASE_URL` check (fixing a latent bug where `.env` variables were not
  loaded when that check ran).
- `repopulate_db.py --regen` safety guard changed from a negative check
  (`"5432" in url and "5434" not in url`) to a positive check — URL must contain
  `5434` or `traininglogs_regen`; this was blocking Supabase cloud URLs.
- Unused `exercise_e1rm_trend` tests removed from `test_queries.py` (query and
  dashboard section were both dropped).

### Validation rules in effect

- `failure_technique` is only valid on sets where `rpe == 10`.
- Exercise `number` fields must be sequential starting at 1.
- `week` must be between 1 and `program_length_weeks` (when program context is present).
- RPE must be a whole or half step between 1 and 10.
- `rest.minutes` must be 0–15; `rest.seconds` must be 0–900; both cannot be set simultaneously.
- Required string fields reject empty or whitespace-only values.

---

## [1.0.0] - 2026-05-05

Initial tagged release. Seed entry — describes the system as it stands at v1.0.0.

### Added

- **Pydantic v2 data model** (`models/models.py`) as the canonical schema.
  Root type `TrainingSession` with nested `Exercise`, `WorkingSet`, `WarmupSet`,
  `Goal`, `RepRange`, `RepCount`, and a `FailureTechnique` discriminated union
  covering myo-reps, lengthened-partials, static holds, and drop sets.
- **Markdown parser** (`parser/extract.py`, `parser/parse.py`) — rule-based,
  deterministic, no LLM in the hot path.
- **Processor CLI** (`processor/processor.py`) — DB-first, JSON-second.
  Errors on `session_id` collision rather than silently overwriting.
- **PostgreSQL storage** with four tables: `sessions`, `exercises`,
  `working_sets`, `warmup_sets`. Cascading deletes on `session_id`.
  `failure_technique` stored as JSONB matching the discriminated union shape.
- **JSON snapshots** written to `output_training_logs_json/` after every DB
  insert, derived from `session.model_dump(mode="json")`.
- **FastAPI REST API** (`api/app.py`) with `X-Api-Key` auth (fails at startup
  if `API_KEY` is unset). Three endpoints:
  - `GET /sessions` — list, filterable by phase, week, and date range.
  - `GET /sessions/{session_id}` — full session detail.
  - `GET /exercises/{name}/history` — per-exercise working-set history.
- **Static dashboard** (`cli/dashboard.py`) — single HTML file with inline
  JSON and Chart.js, rendered into the nine-section "Training Almanac" layout.
  Built from 11 SQL aggregations in `analytics/queries.py`.
- **`traininglogs log` workflow** (`cli/log.py`) — parses a phase/week of
  markdown, inserts to DB, writes JSON snapshots, commits, rebuilds the
  dashboard, and (with `--publish`) pushes the dashboard to the website repo.
- **Test suite** — real Postgres test DB via Docker (no DB mocks), pytest.
- **CI** — GitHub Actions runs the test suite on push and PR.
- **Technical design doc** at `docs/design.html`.

### Validation rules in effect

- `failure_technique` is only valid on working sets where `rpe == 10`.
- Exercise `number` fields must be sequential starting at 1.
- `week` must be between 1 and `program_length_weeks`.
- RPE must be a whole or half step between 1 and 10.
- `rest_minutes` and `actual_rest_minutes` must be between 0 and 15.
- Required string fields reject empty or whitespace-only values.

[Unreleased]: https://github.com/apoorvasharma007/traininglogs/compare/v4.1.0...HEAD
[4.1.0]: https://github.com/apoorvasharma007/traininglogs/compare/v4.0.0...v4.1.0
[4.0.0]: https://github.com/apoorvasharma007/traininglogs/compare/v3.1.0...v4.0.0
[3.1.0]: https://github.com/apoorvasharma007/traininglogs/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/apoorvasharma007/traininglogs/compare/v2.0.0...v3.0.0
[2.0.0]: https://github.com/apoorvasharma007/traininglogs/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/apoorvasharma007/traininglogs/releases/tag/v1.0.0
