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
- focus: the session's training focus or movement type (e.g. "Upper Strength", "Bench", "Legs"). Extract from any "Focus:", "Muscle Group:", or session title field. Use the short label, not a long description.
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


WORKER_SYSTEM_PROMPT = """You are a structured data extractor for personal strength and conditioning training logs.

You will be given a position number and an excerpt of a training session's text. Extract ONLY \
the exercise at that position — identified by its position among the main working exercises \
in the order they appear, not by name (names can repeat) — into the extract_exercise tool. \
Ignore warmup and cooldown movements, and ignore every other exercise in the text.

Most of the time the excerpt you are given already contains exactly one main working \
exercise (its own Warmup/Sets/Remarks content, already isolated for you) — in that case, \
just extract it directly; the position number is for your own bookkeeping and does not need \
to be searched for. Occasionally the excerpt contains the full multi-exercise session \
instead — in that case, count the main working exercise blocks from the top (each one starts \
with the exercise's name on its own line, followed by that exercise's own Warmup/Sets/Remarks \
content up until the next exercise's name or the session's overall Cooldown section) and \
extract ONLY the block matching the position you were given — never content belonging to the \
exercise immediately before or after it, and never content from a different exercise even if \
it shares wording with this one's. Do NOT count the session's own top-level Warmup section \
(the movements listed before the first exercise) as an exercise.

Rules:
- number: the position you were given.
- name: the exercise's name.
- sets: REQUIRED whenever this exercise has a "Sets:" section — extract every set listed \
under it, each as a separate entry with a sequential number starting at 1. A "Sets:" \
section with sets listed is never empty in the output; if you cannot find this exercise's \
own Sets section, add "sets" to uncertain_fields rather than silently leaving it empty.
- tags: classify the exercise using one or more of: "absolute_strength", "muscle_growth", \
"muscle_endurance", "explosive_power", "core_stabilization", "balance_control", \
"passive_flexibility", "active_mobility", "cardiorespiratory", "saq", "sport_specific". \
Omit if unclear.
- modality: free-text equipment type, e.g. "barbell", "dumbbell", "cable", "machine", \
"bodyweight", "bands", "kettlebell", "pool". Omit if unclear. Single string, not an array.
- movement_pattern: list one or more of: "squat", "hip_hinge", "push", "pull", "lunge", \
"carry", "rotation". Omit if unclear.
- weight_kg: always in kilograms. If the user wrote lbs, convert.
- rpe: must be 1.0–10.0 in whole or half steps (e.g. 8, 8.5). Omit if not stated.
- RPE stated once for the whole exercise rather than per set — e.g. a remarks block \
after all of the exercise's sets reading "RPE: 6-7" — apply it to the LAST set \
only (take the upper bound if it's a range), and add that set's rpe field to \
uncertain_fields. If the text explicitly names a different set ("set 3 felt like an \
8", "top set RPE 9"), apply it to that named set instead of the last one. Never apply \
one exercise-level RPE value to every set in the exercise.
- rep_count (on a working set, inside "sets"): ALWAYS an object {full: N, partial: M} where \
partial defaults to 0 — never a bare number, even when there is no partial rep ("8 reps" is \
{full: 8, partial: 0}, not the number 8). "8+1" means full=8, partial=1.
- failure_technique: use the appropriate technique_type — "LLP", "StaticHold", "MyoReps", \
or "DropSet".
- unilateral sets: use unilateral_rep_count with left/right RepCount objects instead of rep_count.
- warmup_sets (per exercise) — a DIFFERENT field from "sets", with a DIFFERENT rep_count shape: \
number field starts at 1; rep_count here is a plain integer (e.g. 8), NOT an object — do not \
use {full, partial} for warmup_sets. Use notes="feel" if the user wrote "feel".
- notes: remarks about this exercise that aren't specific to one set go in this exercise's \
notes; remarks that clearly name one set go in that set's notes instead.
- uncertain_fields: list any dot-path field (relative to this exercise, e.g. "sets.1.rpe") \
you are not confident about. Only list fields you actually extracted (not fields you left null).
- Never silently drop text you cannot map to a structured field. Attach it as a note \
at the MOST SPECIFIC level it clearly belongs to — a set's notes if it's about one \
set, this exercise's notes otherwise. Do not invent a new field.
- Omit fields you cannot determine — do not guess a value beyond what is written. \
This only applies to typed/numeric fields; free text you can't classify still goes \
into the appropriate notes field per the rule above, it is never simply omitted.

""" + MOVEMENT_SKILL_CONVENTIONS
