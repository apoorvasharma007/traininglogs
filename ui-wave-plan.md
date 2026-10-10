# UI wave 1

Started 2026-10-10. A batch of bugs and improvements from using the app, built together, tested
together on staging, released to `main` together.

## Goal

The app should never show a raw error, should always show that it's working while it waits for
the server, and should make the common things (warm-up sets, effort after a set, opening and
closing an exercise) take as few taps as possible and look good doing it. Then a screen-by-screen
audit for consistency and fewer taps, with Apoorva picking which fixes go in.

## Blast radius

| Area | Files |
|---|---|
| Errors | `frontend/src/lib/api.ts`, `auth.ts`, every screen that shows an error; `src/traininglogs/agent/extraction.py`, `validation_card_builder.py` |
| Busy states | Every button that calls the server |
| Warm-ups | `frontend/src/components/SetSheet.tsx` (Build Up to Working Weight), `frontend/src/lib/session.ts` |
| Effort sheet | `frontend/src/screens/session/ExerciseCard.tsx`, `Session.tsx`, a new sheet component |
| Collapse | `frontend/src/screens/session/ExerciseCard.tsx` |
| Audit | All 13 screens |
| Prod data | One exercise note (30 Sep "Strength", Barbell Clean), with approval |

The look is locked: items 4, 5 and 6 change it and need Apoorva's yes on a mock-up or a
description first.

## Branches

Base `ui/wave-1` from `dev`. One sub-branch per step, `ui/wave-1-N-<step>`, squashed into the
base with the full suite green (0 failed, 0 skipped). The base merges into `dev` when every step
is done; Apoorva tests it on staging; then one release to `main`.

## Steps

- [x] 1. **No raw errors on screen.** One function turns any error into a plain sentence; every
  screen uses it. The review card says the exercise couldn't be read instead of showing the
  model's error, and a confirmed session never stores that error in its notes. Clean the one
  existing note in prod (show the row and the statement first).
- [ ] 2. **Busy states.** Every button that calls the server is disabled while it waits and says
  what it's doing in words that fit the action ("Saving…", "Sending…", "Signing in…").
- [ ] 3. **Warm-up sets in one step.** Redesign Build Up to Working Weight: the obvious action is
  "Add N warm-up sets" (blank weights, filled in later). Below it, optionally, a working weight
  turns the same N into a ramp, shown as a ladder before adding. Weights round to 2.5 kg, or
  5 lb when the unit is lb. The warm-up templates stay as they are.
- [ ] 4. **Effort after every working set**, as a bottom sheet like the set menu so it is never
  hidden by an exercise folding away. Swipe down to skip. Colourful and engaging enough that
  people answer it. Mock-up first.
- [x] 5. **Completed exercises open and close every time**, with a smooth height animation.
- [ ] 6. **Screen-by-screen audit**: inconsistencies, extra taps, abrupt loads and transitions,
  one line each. Apoorva picks the fixes per screen.

## ▶ Resume here

2026-10-10: plan written; base `ui/wave-1` cut from `dev` at `2e7b5a5` (includes release 5.0.0
bump). Steps 1 and 5 done and squashed into `ui/wave-1`. Next: step 6 audit report (Apoorva picks fixes),
then steps 2, 3, 4. Worktree: `../traininglogs-wave`. Before merging the wave into `dev`: check it in a
browser against the local app (repo rule), and get Apoorva's yes to clean the one prod note
(30 Sep "Strength", Barbell Clean).
