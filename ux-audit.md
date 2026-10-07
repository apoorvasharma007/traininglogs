# UX Audit: v4.1.0

This document records all UX improvements from the two-round audit (October 2026), deployed as v4.1.0.

## Philosophy

Simplicity and minimal taps. Navigation smooth and easy, uncluttered and straightforward — designed like Apple: clean, purposeful, no noise.

---

## Round 1: Core redesigns

### Home screen
- **Renamed app title** from "Training Logs" was already correct in title; confirmed consistency across home icon and browser tab.
- **Added home-screen icon** (180×180 PNG `apple-touch-icon.png`) so the app installs with a visible icon on iOS home screen.
- **Redesigned home tiles** — "Ad-hoc Workout" and "Wrote it down?" now sit side-by-side instead of stacked, saving vertical space and making the layout tighter. The next-workout tile remains full-width above them and sized to fit content without forcing page scroll even with 10+ exercises.
- **Removed "Now:" label and set count** from resume card — cleaner, less noise.

### Session header
- **Removed second header line** that showed current exercise and set count — simplified the header to focus on session state without extra detail.

### Set sheet
- **Fixed effort area spacing** — changed from fixed h-[12.5rem] to min-h-38 with flex layout to match content height naturally.
- **Removed line under Moderate effort** — removed the "means" text beneath each effort label since it's obvious.
- **Changed "All out" to "All Out"** — Title Case consistency.
- **Added set note placeholders** — distinguish "Working Set Note" and "Warm-up Set Note" so the user knows which type of set they're logging.
- **Removed RPE scroll bar** — hidden with scrollbar-none utility for a cleaner look.
- **Added hidden "Build Up to Working Weight" row** — expands to show warm-up ramp controls when needed, keeping the default state compact. Same height as working-set tab for visual consistency.

### Notes input
- **Created NoteBox component** — textarea expands as user types instead of forcing scroll, feels more responsive.
- **Restored cost text** — included AI cost display on LogFromNotes page without extra visual clutter.

### Exercise lists
- **Changed dot-separated text to numbered lists** — Programs and WorkoutPlan now show exercises and movements as "1. Exercise A", "2. Exercise B" etc., easier to scan than "Exercise A • Exercise B • Exercise C".
- **Grid layout for exercises** — improved readability on screens with multiple exercises.

### Warm-up ramp
- **No switch toggle** — user taps "Build Up to Working Weight" to open the ramp controls, simpler interaction.

---

## Round 2: Refinements and data display

### Resume card time format
- **Changed TIME from 24-hour to 12-hour with AM/PM** — familiar format, easier to read at a glance (e.g., "Started at 3:45 PM" not "15:45").

### Saved session display
- **Added program and workout name to SessionView header** — shows "Workout Name" with "Program Name" underneath using the historyName() helper, so you see where the session came from.
- **Added program metadata to SessionDetail schema** — program_name, workout_position, workout_name, source_kind fields now in the API response.

### Lift chart
- **Removed "From...on..." line** under estimate — less noise, the graph and bold 1RM estimate at the top are enough.
- **Redesigned sessions list as table** — DATE, SET, RPE columns instead of a list, much faster to scan. Shows where each data point came from.
- **Added "Record" tag** at row end — gently marks best performance without being loud.
- **Range buttons hidden until history exceeds 4 weeks** — keeps the interface quiet until you have enough data to compare ranges.

### Settings
- **Added app version display** — shows the version number at the bottom of Settings, matches the /config endpoint for debugging.

---

## Title Case pass

Applied consistent Title Case to all menu labels and buttons across the app:
- "New program" → "New Program"
- "Add workout" → "Add Workout"
- "Deload reminder" → "Deload Reminder"
- "Deload due" → "Deload Due"
- "Easy cardio" → "Easy Cardio"
- "Remove exercise" → "Remove Exercise"

---

## Testing and rollout

- **120 tests passed** across all rounds, verifying layout, text, and interaction changes.
- **Consistency verified** — changes applied uniformly across all affected screens.
- **Deployed to staging** for user review and feedback.
- **Merged to production** as v4.1.0 on 2026-10-08.

---

## Impact

These changes reduce visual noise, lower interaction complexity, and make navigation more fluid. The app feels less crowded and more intentional. Data is displayed only when it helps decision-making; labels and hints disappear when context makes them obvious.
