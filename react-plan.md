# React app plan (Phase 8)

## Goal

Replace the vanilla `web/` page with a React app and add programs, planned workouts and live
sessions. Today the app can only log a session from notes through AI. After this phase it can also
log a session by hand while training, follow a program that tells you the next workout, and remind
you to deload. The session in progress is saved on the phone the whole time and sent to the server
once, at Finish.

Design (approved 2026-10-04): https://claude.ai/artifact/CTA5h3g9DweowJ4eF6wZmK
Colours (option A chosen): https://claude.ai/artifact/PfpFp59fEahi3LQV5pJe6y

## Terms

| Term | Means |
|---|---|
| Program | An ordered list of workouts. After the last one it starts again at workout 1. You follow one program at a time. |
| Workout | A planned item in a program: a number, an optional name ("Push"), exercises, number of sets and target reps. Weights are not stored; they come from last time. |
| Session | What you actually did. Starting a workout or a blank workout creates a session in progress; Finish saves it to History. |
| Deload | The next pass through the program (one session per workout) with lighter weights. |

"Routine" is not used anywhere.

## Decisions

- Tabs: Train, Programs, Progress, History, Settings.
- Home: one-line deload alert; card with the current program on top and the next workout below;
  buttons "Blank workout" and "Log from notes".
- Next workout is the one after the last session that came from the followed program.
- Deload reminder: default 28 days, set per program. Counts from the program start or the end of the
  last deload. A 7-day break with no training restarts the count. Alert has Start and ✕ (remind in 7 days).
- Session screen: last time's values in a LAST column; values carried from last time are grey until
  ticked or edited. Last time's note is grey with a clock icon, no date. Today's note is added from
  the ⋯ menu and shows as a bordered field. A note can be pinned; pinned notes show on that exercise
  in every later session.
- Editing: tap a set to open a bottom sheet (±2.5 kg, ±1 rep, type a number, RPE row, warmup or
  working, note, delete with Undo). ⋯ menu per exercise: add warmup set, add set, add note, rename,
  remove. "+ Exercise" adds a blank card with a name field; no search or picker.
- Finish: ticked sets are saved, unticked sets are left out. If offline, the session waits on the
  phone and sends itself later. If the session differs from its workout, Finish asks whether to
  update the workout.
- Log from notes: a pasted session counts as the next workout unless "Not part of the program" is picked.
- Review (after Log from notes) uses the same editor as the session screen.

## Look

Fonts: Geist and Geist Mono. Icons: Lucide. Sheets: shadcn drawer. Motion: Motion library and the
View Transitions API, all off when the phone asks for reduced motion. Light and dark follow the phone.

| Token | Dark | Light |
|---|---|---|
| background | `#0B0B0C` | `#FAFAFA` |
| card | `#161618` | `#FFFFFF` |
| border | `#26262A` | `#E4E4E7` |
| text | `#F4F4F5` | `#18181B` |
| text-secondary | `#8E8E96` | `#71717A` |
| text-tertiary | `#5C5C63` | `#A1A1AA` |
| button | `#F4F4F5` on `#0B0B0C` text | `#18181B` on `#FFFFFF` text |
| accent (`highlight` in code) | `#4CC38A` | `#15803D` |
| accent-soft (`highlight-soft` in code) | `#13261C` | `#F0FDF4` |
| warning | `#D4A24C` on `#1F1A10` | `#92400E` on `#FFFBEB` |
| danger | `#E5484D` | `#B91C1C` |

The accent appears only on ticked sets, the "Next" chip, records and the active tab.

## Blast radius

- New: `frontend/` (Vite, React, TypeScript, Tailwind, shadcn/ui, TanStack Query, Vitest).
- `Dockerfile`: add a Node build stage; copy `frontend/dist` instead of `web/`.
- `src/traininglogs/api/app.py`, `schemas.py`: serve the built app; new endpoints for programs,
  workouts, last-time values, pinned notes and saving a session without AI.
- `src/traininglogs/db/`: new tables and queries. Prod database migration in step 3.
- `.github/workflows/ci.yml`: frontend type-check, tests and build.
- Removed in step 8: `web/`.
- Docs: README, CLAUDE.md, docs/design.html, roadmap.md.

## Steps

Base branch `phase-8/react` from `dev`. One sub-branch per step, `phase-8/react-N-<step>`, squash-merged
into the base when the suite is 0 failed and 0 skipped. The base merges to `dev` when all steps are done.

- [x] 1. `scaffold`: `frontend/` app with the tokens above, five tabs, empty screens. FastAPI serves
      the build. Dockerfile builds it. CI runs type-check, Vitest and build. `web/` still works.
- [x] 2. `port`: Progress, Lift, History, Settings, Log from notes and Review in React. Review gets
      the bottom-sheet editor and ⋯ menu on top of the existing `/edit` endpoint.
- [x] 3. `programs-db`: tables `programs`, `program_workouts`, `program_workout_exercises`; sessions get
      a link to their workout and a deload flag; pinned notes stored per exercise name. Prod migration
      needs Apoorva's approval of the exact SQL, a backup, one transaction, counts before and after.
- [x] 4. `programs-ui`: Programs tab, program screen, workout plan screen, follow and stop following.
- [x] 5. `session`: live session saved in the browser database (IndexedDB), last-time values and notes,
      pinned notes, Finish sends one request to a new endpoint that saves a confirmed session without
      AI, retry when offline.
- [x] 6. `home`: next workout, deload reminder, blank workout, in-progress and waiting-to-send states.
- [x] 6b. `options`: a plan line can list alternatives ("Shoulder Press or Bench press"). Start
      picks the one done longest ago; the session shows just that one and stays fully editable
      (rename suggests the alternatives). No toggles. Adds Starting Strength Phase 4 as 3 workouts.
- [ ] 7. `polish` (moved after the deploy, to be shaped by real use; its first fixes are merged): loading and empty states, transitions, a last pass on motion.
- [x] 8. `retire-web`: delete `web/`, update docs, merge `phase-8/react` into `dev`. Deploying is
      Apoorva's call.
      At the deploy (with its own approval): `UPDATE raw_inputs SET source_kind = 'text' WHERE
      source_kind = 'markdown'` (rows the old live app wrote meanwhile), then replace the check
      with `source_kind IN ('text', 'manual')`, matching `schema.sql`.

## ▶ Resume here

2026-10-04: 4.0.0 is live on Cloud Run (CD run 37165158828). Steps 1 to 6b and 8 are done and in
`main`. The `source_kind` check in prod is `text`/`manual`, matching `schema.sql` (backup
`backups/prod-before-source-kind-check-2026-10-04.json`).
Next: step 7 (`polish`) once Apoorva has trained with the app; collect what feels off first.
