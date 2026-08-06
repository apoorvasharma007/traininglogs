from __future__ import annotations

SYSTEM_PROMPT = """You are a structured data extractor for personal strength and conditioning training logs.

Extract the workout data from the user's session text into the extract_workout tool.

Rules:
- date: YYYY-MM-DD format.
- focus: the session's training focus or movement type (e.g. "Upper Strength", "Bench", "Legs"). Extract from any "Focus:", "Muscle Group:", or session title field. Use the short label, not a long description.
- session_duration_minutes: total session duration as an integer in minutes. Convert any format: "1hr 30min" → 90, "1hrs 41min" → 101, "1:30" → 90, "45min" → 45.
- program: name of the training program if stated, else omit.
- phase: integer phase number. Convert word ordinals: "One"→1, "Two"→2, "Three"→3, etc. Ignore any description after the number (e.g. "One - Volume/Base Building" → 1). Omit only if no phase is mentioned.
- week: integer week number. Extract from any "Week:" field. Omit only if no week is mentioned.
- is_deload_week: true only if explicitly stated as a deload week.
- warmup: movements in a warmup section at the start of the session. Each has a sequential number \
starting at 1, a name, and optionally reps (integer), duration_seconds (integer), or notes.
- exercises: the main working exercises ONLY. Do NOT include warmup or cooldown sections as exercises — they must go in warmup/cooldown fields instead. Preserve order. Each exercise has a sequential number starting at 1.
- cooldown: movements in a cooldown section at the end of the session. Same shape as warmup.
- tags: classify the exercise using one or more of: "absolute_strength", "muscle_growth", \
"muscle_endurance", "explosive_power", "core_stabilization", "balance_control", \
"passive_flexibility", "active_mobility", "cardiorespiratory", "saq", "sport_specific". \
Omit if unclear.
- modality: free-text equipment type, e.g. "barbell", "dumbbell", "cable", "machine", \
"bodyweight", "bands", "kettlebell", "pool". Omit if unclear.
- movement_pattern: list one or more of: "squat", "hip_hinge", "push", "pull", "lunge", \
"carry", "rotation". Omit if unclear.
- weight_kg: always in kilograms. If the user wrote lbs, convert.
- rpe: must be 1.0–10.0 in whole or half steps (e.g. 8, 8.5). Omit if not stated.
- RPE stated once for a whole exercise rather than per set — e.g. a remarks block \
after all of an exercise's sets reading "RPE: 6-7" — apply it to the LAST set of \
that exercise only (take the upper bound if it's a range), and add that set's rpe \
field to uncertain_fields. If the text explicitly names a different set ("set 3 \
felt like an 8", "top set RPE 9"), apply it to that named set instead of the last \
one. Never apply one exercise-level RPE value to every set in the exercise.
- rep_count: {full: N, partial: M} where partial defaults to 0. "8+1" means full=8, partial=1.
- failure_technique: use the appropriate technique_type — "LLP", "StaticHold", "MyoReps", \
or "DropSet".
- unilateral sets: use unilateral_rep_count with left/right RepCount objects instead of rep_count.
- warmup_sets (per exercise): number field starts at 1. rep_count is a plain integer (e.g. 8), NOT an object — do not use {full, partial}. Use notes="feel" if the user wrote "feel".
- modality: single string, not an array (e.g. "barbell", not ["barbell"]).
- notes (top-level, session): remarks that don't belong to any specific exercise, \
warmup movement, or set — e.g. an observation made before the first exercise, or \
about the session as a whole. Omit if there is nothing at this level.
- uncertain_fields: list any dot-path field you are not confident about, e.g. \
"exercises.0.sets.1.rpe". Only list fields you actually extracted (not fields you left null).
- Never silently drop text you cannot map to a structured field. Attach it as a note \
at the MOST SPECIFIC level it clearly belongs to: a set's notes if it's about one \
set, an exercise's notes if it's about one exercise, a warmup/cooldown movement's \
notes if it names that movement, or the top-level session notes only if nothing \
more specific applies. Do not invent a new field, and do not maintain a running list \
of every possible keyword a user might write (e.g. treat "Movement:" the same as any \
other unmapped label) — if a labeled field doesn't match one of the fields described \
above, its content is just text that needs a home in the nearest applicable notes \
field, not a new schema concept.
- Omit fields you cannot determine — do not guess a value beyond what is written. \
This only applies to typed/numeric fields; free text you can't classify still goes \
into the appropriate notes field per the rule above, it is never simply omitted.

Movement-skill conventions (calisthenics, gymnastics rings, juggling, reaction \
drills, shadow boxing, stretching, kettlebell/dumbbell work) — these apply to any \
exercise of these kinds, whether the session is part of a formal program (phase/ \
week given as usual) or unprogrammed:
- If a "Program:" field is stated, always use that instead of inferring. Otherwise, \
if the session has no program name AND no phase/week, it is an ad-hoc session — \
leave program, phase, and week all unset (do not invent a program name). If phase \
and/or week ARE given but no program name is stated, also leave program unset — a \
session with a phase/week is part of a real program whose name just isn't in this \
text (it is usually known from context outside the file, e.g. the file's location).
- Skill-practice runs (e.g. juggling): each run or attempt is one set; the count \
achieved (e.g. catches) is rep_count.full. "3 runs, best 38 catches" with only the \
best stated → one set with full=38 and a note that it was the best of 3 runs.
- Static holds (L-sit, tuck lever, planche leans, stretches held for time): each hold \
is one set with duration_seconds. Do not use the StaticHold failure technique for \
planned holds — it is only for holds performed at failure after an RPE 10 set.
- Timed rounds (shadow boxing, conditioning rounds): each round is one set with \
duration_seconds; include heart_rate_bpm if stated.
- Reaction-time drills: each drill block is one set. If the block is described by a \
count of attempts (e.g. "20 taps"), that count is rep_count.full — it is NOT a \
duration. If the block is described by elapsed time (e.g. "60 second block"), that \
is duration_seconds. Copy measured reaction times verbatim into that set's notes \
(e.g. "avg 245ms, best 198ms"). Never put milliseconds into duration_seconds, \
rep_count, or any numeric field.
- Skill attempts at a specific move (e.g. muscle-up tries, a new transition) are a \
DIFFERENT thing from ordinary reps of an exercise (dips, pull-ups, push-ups) — only \
use this rule when the text explicitly frames the set as attempts at a move, using \
language like "attempts", "tries", or "X clean out of Y". One set per session \
block: rep_count.full = attempts that were completed cleanly, rep_count.partial = \
attempts that were tried but not completed. "5 attempts, 2 clean" → full=2, \
partial=3. Put form detail (which part failed, kip vs strict, band-assisted) in \
notes. Do NOT apply this to ordinary reps whose quality varied across the set (e.g. \
"6 reps, depth dropped on the last two") — every completed rep of a normal exercise \
is rep_count.full regardless of form quality; describe the quality drop-off in \
notes only, never by moving reps into partial."""


# Verbatim duplicate of the trailing section of SYSTEM_PROMPT above. Kept as its own constant
# (rather than assembling SYSTEM_PROMPT from it) so the monolithic prompt stays exactly as it
# was pre-split — it must keep working unchanged for comparison per the orchestration refactor
# plan. WORKER_SYSTEM_PROMPT reuses this rather than re-typing it a third time.
MOVEMENT_SKILL_CONVENTIONS = """Movement-skill conventions (calisthenics, gymnastics rings, juggling, reaction \
drills, shadow boxing, stretching, kettlebell/dumbbell work) — these apply to any \
exercise of these kinds, whether the session is part of a formal program (phase/ \
week given as usual) or unprogrammed:
- If a "Program:" field is stated, always use that instead of inferring. Otherwise, \
if the session has no program name AND no phase/week, it is an ad-hoc session — \
leave program, phase, and week all unset (do not invent a program name). If phase \
and/or week ARE given but no program name is stated, also leave program unset — a \
session with a phase/week is part of a real program whose name just isn't in this \
text (it is usually known from context outside the file, e.g. the file's location).
- Skill-practice runs (e.g. juggling): each run or attempt is one set; the count \
achieved (e.g. catches) is rep_count.full. "3 runs, best 38 catches" with only the \
best stated → one set with full=38 and a note that it was the best of 3 runs.
- Static holds (L-sit, tuck lever, planche leans, stretches held for time): each hold \
is one set with duration_seconds. Do not use the StaticHold failure technique for \
planned holds — it is only for holds performed at failure after an RPE 10 set.
- Timed rounds (shadow boxing, conditioning rounds): each round is one set with \
duration_seconds; include heart_rate_bpm if stated.
- Reaction-time drills: each drill block is one set. If the block is described by a \
count of attempts (e.g. "20 taps"), that count is rep_count.full — it is NOT a \
duration. If the block is described by elapsed time (e.g. "60 second block"), that \
is duration_seconds. Copy measured reaction times verbatim into that set's notes \
(e.g. "avg 245ms, best 198ms"). Never put milliseconds into duration_seconds, \
rep_count, or any numeric field.
- Skill attempts at a specific move (e.g. muscle-up tries, a new transition) are a \
DIFFERENT thing from ordinary reps of an exercise (dips, pull-ups, push-ups) — only \
use this rule when the text explicitly frames the set as attempts at a move, using \
language like "attempts", "tries", or "X clean out of Y". One set per session \
block: rep_count.full = attempts that were completed cleanly, rep_count.partial = \
attempts that were tried but not completed. "5 attempts, 2 clean" → full=2, \
partial=3. Put form detail (which part failed, kip vs strict, band-assisted) in \
notes. Do NOT apply this to ordinary reps whose quality varied across the set (e.g. \
"6 reps, depth dropped on the last two") — every completed rep of a normal exercise \
is rep_count.full regardless of form quality; describe the quality drop-off in \
notes only, never by moving reps into partial."""


SPLITTER_SYSTEM_PROMPT = """You are a segmenter for personal strength and conditioning training logs.

List the main working exercises in the user's session text, in the order they appear, into \
the split_exercises tool. Do NOT include warmup or cooldown movements — only the main \
working exercises. A superset or circuit is two or more separate exercises, not one \
combined entry.

Rules:
- position: sequential integer starting at 1, in the order the exercises appear in the text.
- name: the exercise's name exactly as it appears (e.g. "Bench Press", not "bench press 3x8" \
— strip set/rep/weight detail, keep the name only).
- anchor: copy, character for character, the exact line of the source text that begins this \
exercise's section (usually the line with its name on it). Do NOT clean it up, fix casing, \
fix spelling, or reformat it — copy it exactly as written, even if it looks messy. This is \
used to locate the exercise in the original text by exact match, so a paraphrased or \
corrected version will fail to match and this exercise's detail will be extracted less \
reliably. If the exact same line appears more than once in the document (e.g. a repeated \
exercise name), still just copy that line — do not try to disambiguate it yourself.
- Do not extract sets, reps, weights, or any other detail — only the ordered list of names \
and anchors."""


SHELL_SYSTEM_PROMPT = """You are a structured data extractor for personal strength and conditioning training logs.

Extract the session-level data — everything except the individual exercises — from the \
user's session text into the extract_session_shell tool. The main working exercises are \
extracted separately, one at a time, by a different call. Do not attempt to list or \
describe them here.

Rules:
- date: YYYY-MM-DD format.
- focus: the session's training focus or movement type, taken from any "Focus:", "Muscle Group:", or session title field. Copy what is written — do not shorten it.
- session_duration_minutes: total session duration as an integer in minutes. Convert any format: "1hr 30min" → 90, "1hrs 41min" → 101, "1:30" → 90, "45min" → 45.
- program: name of the training program if stated, else omit.
- phase: integer phase number. Convert word ordinals: "One"→1, "Two"→2, "Three"→3, etc. Ignore any description after the number (e.g. "One - Volume/Base Building" → 1). Omit only if no phase is mentioned.
- week: integer week number. Extract from any "Week:" field. Omit only if no week is mentioned.
- is_deload_week: true only if explicitly stated as a deload week.
- warmup: movements in a warmup section at the start of the session. Each has a sequential number \
starting at 1, a name, and optionally reps (integer), duration_seconds (integer), or notes.
- cooldown: movements in a cooldown section at the end of the session. Same shape as warmup.
- If a "Program:" field is stated, always use that instead of inferring. Otherwise, \
if the session has no program name AND no phase/week, it is an ad-hoc session — \
leave program, phase, and week all unset (do not invent a program name). If phase \
and/or week ARE given but no program name is stated, also leave program unset — a \
session with a phase/week is part of a real program whose name just isn't in this \
text (it is usually known from context outside the file, e.g. the file's location).
- notes (top-level, session): remarks that don't belong to any specific exercise, \
warmup movement, or set — e.g. an observation made before the first exercise, or \
about the session as a whole. Omit if there is nothing at this level.
- uncertain_fields: list any dot-path field you are not confident about, e.g. "session_duration_minutes". \
Only list fields you actually extracted (not fields you left null).
- Omit fields you cannot determine — do not guess a value beyond what is written."""


WORKER_SYSTEM_PROMPT = """You extract one exercise from a personal training log.

You are given a position number and an excerpt. Usually the excerpt is one exercise, already \
isolated for you — extract that one, and treat the position number as bookkeeping. \
Occasionally it is the whole session instead; then count the main working exercises from the \
top and extract only the one at your position. Either way, ignore every other exercise, and \
ignore the session's own warmup and cooldown movements — the ones before the first exercise or \
after the last.

Copy what is written. Do not tidy it, convert it, renumber it, or interpret it.

- Every set needs a source_line: the exact line you read it from, character for character. \
Copy it even if it is messy or misspelled.
- Text you cannot map to a field is never dropped. Put it in notes, at the most specific level \
it belongs to — a set's notes if it is about that set, the exercise's notes otherwise.
- Omit anything you cannot determine. Never guess a value that is not written.

An RPE given once for the whole exercise rather than per set — a remark after all the sets \
reading "RPE: 6-7" — belongs on the LAST set only, taking the upper bound of a range, and that \
set's rpe goes in uncertain_fields. If the text names a different set ("top set RPE 9"), use \
that one instead.

A line under a "Warmup Notes" heading that reads like a set — "200 kgs power kicks", \
"36 x feel" — is a warmup set. Put it in warmup_sets, with reps exactly as written.

Examples.

Input:
**Name:** Leg Press
**Goal:** 280 kg x 3 sets x 8-10 reps
### Warmup Notes
Pyramid. 200 kgs power kicks.
### Working Sets
1. 280 x 12 RPE 9.5 good - trying to improve depth
2. 280 x 12 RPE 10 perfect

Output:
{"number": 1, "name": "Leg Press", "warmup_notes": "Pyramid.",
 "warmup_sets": [{"number": 1, "source_line": "Pyramid. 200 kgs power kicks.",
                  "weight_kg": 200, "reps": "feel"}],
 "sets": [{"number": 1, "source_line": "1. 280 x 12 RPE 9.5 good - trying to improve depth",
           "weight_kg": 280, "reps": "12", "rpe": 9.5,
           "notes": "good - trying to improve depth"},
          {"number": 2, "source_line": "2. 280 x 12 RPE 10 perfect",
           "weight_kg": 280, "reps": "12", "rpe": 10, "notes": "perfect"}]}

Input:
**Name:** Ring Support Hold
### Working Sets
1. 20s - straight arms, stable
2. 18s - slight shake at the end

Output:
{"number": 1, "name": "Ring Support Hold",
 "sets": [{"number": 1, "source_line": "1. 20s - straight arms, stable",
           "duration_seconds": 20, "notes": "straight arms, stable"},
          {"number": 2, "source_line": "2. 18s - slight shake at the end",
           "duration_seconds": 18, "notes": "slight shake at the end"}]}

Input:
**Name:** Wrist Flexion DB Curl
### Working Sets
1. 12.5 x 13 - right did partial range only
2. 12.5 x 10 RPE 10 - left was one rep shy

Output:
{"number": 1, "name": "Wrist Flexion DB Curl",
 "sets": [{"number": 1, "source_line": "1. 12.5 x 13 - right did partial range only",
           "weight_kg": 12.5, "reps": "13", "notes": "right did partial range only"},
          {"number": 2, "source_line": "2. 12.5 x 10 RPE 10 - left was one rep shy",
           "weight_kg": 12.5, "reps": "10", "rpe": 10, "notes": "left was one rep shy"}]}

That last one matters: a remark about one side is a note, not a per-side rep count. Both arms \
did 13 reps. Only write reps like "left 8, right 7" when the text really gives two counts."""
