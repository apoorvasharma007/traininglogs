# UI wave 1

Started 2026-10-10. A batch of bugs and improvements from using the app, built together, tested
together on staging, released to `main` together.

## Goal

The app should never show a raw error, should always show that it's working while it waits for
the server, and should make the common things (warm-up sets, effort after a set, opening and
closing an exercise, entering last time's numbers) take as few taps as possible and look good
doing it. The screen-by-screen audit (`ui-audit.md`) fixes inconsistencies and extra taps.

## Blast radius

| Area | Files |
|---|---|
| Errors | `frontend/src/lib/api.ts`, `auth.ts`, `errors.ts`, every screen that shows an error; `src/traininglogs/agent/card_edits.py`, `ingest/confirm.py`, `api/app.py` |
| Busy states | Every button that calls the server |
| Warm-ups | `frontend/src/components/SetSheet.tsx`, `frontend/src/lib/session.ts` |
| Effort sheet | `frontend/src/screens/session/Session.tsx`, a new `EffortSheet` component |
| Tap-to-fill, cascade fill | `frontend/src/components/NumberBox.tsx`, `frontend/src/lib/session.ts` |
| Transitions, loading, open/close, press feedback | `frontend/src/App.tsx`, `components/QueryStatus.tsx`, a new `Collapsible` component, every screen |
| Key Lifts | `src/traininglogs/db/schema.sql`, `analytics/progress.py`, `api/app.py`, `frontend/src/screens/Settings.tsx` |
| Prod data | One exercise note (30 Sep "Strength", Barbell Clean); one new column for Key Lifts. Both with approval. |

The look is locked: steps 3, 4 and 6 change it. Apoorva agreed the designs below on 2026-10-10;
step 4 still needs a mock-up first.

## Branches

Base `ui/wave-1` from `dev`. One sub-branch per step, `ui/wave-1-N-<step>`, squashed into the
base with the full suite green (0 failed, 0 skipped). The base merges into `dev` when every step
is done; Apoorva tests it on staging; then one release to `main`.

## Decisions (2026-10-10)

- Weights are kg only. No lb setting in this wave.
- Tap-to-fill for every grey number: the first tap fills it in without the keyboard; a second
  tap opens the keyboard with the number selected, so typing replaces it.
- Cascade fill: a weight or reps typed into a set shows in grey in the empty sets below it.
- Screen transitions are iOS style.
- Later, not this wave: exercise-name cleanup and suggestions (D1), lb units, a rest timer,
  "Save as a workout" from an ad-hoc session.

## Steps

- [x] 1. **No raw errors on screen.** `errorText()` and `ShownError` in `lib/errors.ts`: only the
  server's own wording or a plain sentence reaches the screen. Card edit and correction errors
  send a plain message and log the technical one. A failed exercise reading no longer saves its
  error as the note.
- [x] 2. **Busy states.** Every button that calls the server is disabled (and looks it) while it
  waits, with a word that fits: Start Workout and Ad-hoc Workout ("Starting…"), Repeat
  ("Starting…"), Follow This Program ("Following…"), Stop Following, Deload Save and Update
  Program ("Saving…"). Log from Notes says "Reading your note…" while the AI reads.
- [x] 3. **Warm-up sets in the set sheet.** Build Up to Working Weight becomes "Warm-up Sets":
  - "How many": the − 3 + count.
  - "Work up to": a kg box showing the first working weight (or last time's) in grey. Tap-to-fill
    applies. Empty: the sets are added blank. Filled: a ladder shows under it
    (`40×5 → 60×3 → 80×2`), rounded to 2.5 kg, and the sets are added with those numbers.
  - One button, "Add 3 Sets" (the count changes with the stepper).
  - The exercise menu's Add Warm-up Set and Warm-up Set Templates stay as they are.
- [x] 4. **Effort after every working set.** Ticking a working set (not a warm-up) opens a bottom
  sheet asking how hard it was. Picking an answer saves it and closes the sheet; swiping down
  skips. It never hides behind a folding exercise. Colourful and engaging enough that people
  answer it. Apoorva reviews it on his phone against the local server (in place of a mock-up).
  Added 2026-10-11: a set ticks itself once weight and reps are typed and the keyboard leaves
  the set's row, which then asks for effort.
- [x] 5. **Completed exercises open and close every time**, with the sets sliding in and out.
- [x] 6. **Audit fixes** (`ui-audit.md`):
  - A1. iOS-style transitions: a deeper screen slides in from the right, Back slides it out to the
    right, switching tabs fades. Motion, in `App.tsx`.
  - A2. Loading shows grey outlines shaped like the content, then fades the content in. Replaces
    `Loading` on Train, History, Progress, Lift, Programs, Program and Session view.
  - A3. One `Collapsible` (arrow turns, content slides) for History months, Progress "Other
    lifts", Build Up and exercise cards.
  - A4. Press feedback everywhere: rows darken, buttons shrink.
  - A6. Title Case for every button, sheet title and screen title.
  - A7. Done screen: the change rows tick with the set tick circle instead of phone checkboxes.
  - A8. Each error shows where its action is (the Deload sheet's error inside the sheet).
  - B1. Train's "Create Your Own" opens the new-program name sheet directly.
  - B3. Program shows + Add Workout while viewing, not only in Edit.
  - B4. "Reorder" in the session's exercise menu opens a drag list of names (like a program's
    workouts), replacing Move Up and Move Down.
  - B6. A session row on a lift's page opens that session.
  - B7. Sign in: "Send a New Code" under the code box.
  - B9. Key Lifts in Settings become your own choice: add or remove lifts from your logged
    exercises. Stored per person (a new column, through `.claude/db-migration.md`; the prod SQL
    shown first). Progress shows your chosen lifts first; the built-in list is the default.
  - B10. Settings AI Use shows a placeholder while loading and the error line if it fails.
  - B11. Log from Notes' cost note becomes one line.
- [x] 7. **Tap-to-fill and cascade fill** for set weight and reps (see Decisions). Ticking ✓ still
  accepts all grey numbers at once.
- [x] 8. **Confirm checks first (C1).** On Review, when "N things to check" is showing, Confirm
  Session asks "N things still to check. Save anyway?" with Check Them (jumps to the first) and
  Save Anyway. Nothing flagged: it saves straight away, as now.
- [x] 9. **Ad-hoc sessions named after what you did (D6).** An ad-hoc session's title becomes its
  first exercises ("Squat, Bench Press, Rows"), shown in the session header and History.

## Added during testing (2026-10-11)

Effort colours (Apoorva's palette), solid red destructive buttons, shared buttons, menus, confirm
sheet and section cards, one type/icon/radius scale, frosted sheets and bars, grey header bands, no
dashed styles, fewer divider lines, folded warm-up and cool-down on a workout, a card per program,
the Undo countdown, Key Lifts confirm, agreed copy and "check" wording, and Send Feedback in
Settings (`feedback` table, `POST /feedback`).

## ▶ Resume here

2026-10-11: every step done; suites green (server 737, app 137, 0 skipped); first load 93.8 KB.
Shipping as 5.0.0: changelog folded into 5.0.0. Next: merge `ui/wave-1` into `dev` (staging needs
the new schema: `users.key_lifts`, `feedback`), then prod SQL with Apoorva's yes (both schema
additions, plus clearing the one raw-error note on 30 Sep "Strength", Barbell Clean), then release
`dev` into `main`.
