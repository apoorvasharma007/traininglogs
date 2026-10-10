# UI audit, wave 1 step 6

Done 2026-10-10 by reading every screen (`frontend/src/screens`) and the shared components.
Apoorva picks which findings go into wave 1; the rest wait.

## Across the app

| # | Finding | Fix | Visual? |
|---|---|---|---|
| A1 | No page transitions: every navigation swaps the screen instantly. | A short fade and slide on every route change, in `App.tsx`. | Yes |
| A2 | Loading is a "Loading…" line that pops in, then the content jumps in under it. | Grey outlines shaped like the content while it loads (Train, History, Progress, Lift, Programs, Program, Session view), then fade the content in. | Yes |
| A3 | Four different open/close styles: History months swap the arrow; Progress "Other lifts" turns it; exercise cards use down/up arrows; Build Up turns it. Only exercise cards animate. | One open/close piece (arrow turns, content slides) used everywhere. | Yes |
| A4 | Press feedback differs: some buttons shrink when pressed, some rows darken, many react not at all (History rows, Progress tiles and rows, Session in progress card, Sign Out, Done). | Rows darken, buttons shrink, everywhere. | Small |
| A5 | Buttons with no busy state (step 2): Start Workout, Ad-hoc Workout, Repeat, Follow This Program (disabled but looks the same), Deload Save, Stop Following. Send on Log from Notes says "Sending…" through a 10–30 s AI read. | Step 2: disabled look plus a fitting word; "Reading your note…" for Send. | Small |
| A6 | Mixed capitalisation: "Sign in", "Finish session?", "Discard this session?", "Stop following …?", "New workout", next to "Sign Out?", "Session Done", "New Program". | Title Case everywhere, per the existing rule. | Text only |
| A7 | Done screen uses the phone's own checkboxes; everything else uses the app's own toggles. | Use the app's toggle style. | Small |
| A8 | Program screen shows any failed change under the workout list, even one from the Deload sheet. | Show each error where its action is. | Small |

## Fewer taps, screen by screen

| # | Screen | Finding | Fix |
|---|---|---|---|
| B1 | Train | "Create Your Own" goes to Programs, then New, then Create Your Own, then the name: 4 taps. | Open the name sheet directly: 1 tap. |
| B2 | Programs | New opens a sheet with two choices. | Keep; low value. |
| B3 | Program | Adding a workout needs Edit first, then + Add Workout. | Show + Add Workout while viewing too. |
| B4 | Session | Reordering exercises is Move Up / Move Down, one step per tap, in a 7-item menu. The Program screen already drags to reorder. | Drag to reorder exercises in the session. |
| B5 | Session | Four ways to add warm-ups: menu Add Warm-up Set, menu Warm-up Set Templates, Build Up in the set sheet, turning a set into a warm-up. | Step 3: one Warm-up Sets sheet with "Add N sets", ramp to a weight, and templates; one entry in the menu. |
| B6 | Lift | Session rows can't be tapped. | Tap a row to open that session. |
| B7 | Sign in | No way to get a new code except "Use a Different Email" and retyping. | "Send a New Code" button. |
| B8 | Settings | No kg/lb setting: the app shows and stores kg only, so lb rounding (step 3) has nothing to turn it on. | Decide: add a kg/lb setting (every weight on screen converts; bigger), or keep kg only for now. |
| B9 | Settings | Key Lifts looks like a list you can change, but can't be. | Make it editable, or show it as plain text. |
| B10 | Settings | AI Use is blank while loading and shows nothing if it fails. | Placeholder while loading; the error line if it fails. |
| B11 | Log from Notes | The cost note under Send is three lines long. | One line: "About $0.02–0.06 per note. You check everything before it's saved." |
