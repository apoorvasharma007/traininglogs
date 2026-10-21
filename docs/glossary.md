# Glossary

One name per concept, for docs, plans, issues, commit messages and agent prompts. Code keeps its
current names (renaming columns or fields needs its own decision); the "In code" column maps each
term to them. Where the app shows a different label, that's noted too. Agreed with Apoorva on
2026-10-21.

## Logging from a note

| Term | Meaning | In code | Don't say |
|---|---|---|---|
| note | The text you paste in, written however you like. | `input_text.content` with `kind = 'text'`; `POST /inputs` (`CaptureIn`) | raw input, capture, log text |
| input | The saved record behind any session: a note, a live session or an import. | `input_text` (`kind`: `text`, `manual`, `import`); `source_kind` in the API | |
| AI extraction | What the AI understood from a note: exercises, sets, weights, reps, RPE, as structured data. | `input_text_confirmation_cards.extract`; `TrainingLogLLMExtract`; `/extractions/{id}` | extract (as a noun in prose), parse |
| confirmation card | What you check, fix and confirm, built from the AI extraction. Never shortened to "card", which also means the UI cards on the session screen (`ExerciseCard`, `MovementCard`). | `input_text_confirmation_cards`; `UserValidationCard`; app screen "Review" | card, validation card, review card |
| AI fix | A change to a confirmation card you type as a sentence; the AI turns it into edits. | `POST /extractions/{id}/correct`; `FixBox`; app label "fix" | correction |
| manual edit | A change to a confirmation card you make by tapping a field. | `POST /extractions/{id}/edit`; `card_edits.py` | |
| confirm | Accepting a confirmation card, which saves it as a session. | `POST /extractions/{id}/confirm`; `status = 'confirmed'` | approve, accept |

## Sessions and sets

| Term | Meaning | In code | Don't say |
|---|---|---|---|
| session | What you actually did on one occasion, saved. | `workout_sessions`; `TrainingSession`; `/sessions` | workout session, training session, workout |
| live session | A session you log set by set while training, in the app. Saved with no confirmation card. | `ManualSessionIn`; `kind = 'manual'`; app label "Session in Progress" | manual session |
| exercise | One thing you did in a session, with its sets. | `workout_session_exercises`; `Exercise` | |
| working set | A set that counts toward the exercise's work. | `workout_session_sets`; `WorkingSet` | |
| warm-up set | A lighter set before an exercise's working sets. | `WarmupSet`; app label "Warm-up Sets" | warmup set, warm-up (alone) |
| session warm-up | Movements at the start of a session, before the first exercise. | `workout_session_warmups`; `SessionWarmup`; app label "Warm-up" | warm-up (alone) |
| session cool-down | Movements at the end of a session. | `workout_session_cooldowns`; `SessionCooldown`; app label "Cool-down" | cooldown |
| movement | One item in a session warm-up or cool-down: a name, and reps or a duration or neither ("easy walk"). | `Movement` (API); `program_workouts` warm-up and cool-down lists | |
| RPE | Effort for a set, 1 to 10 in whole or half steps. "Effort" is the app's plain label for it. | `rpe` | effort (in docs and code) |

## Exercises

| Term | Meaning | In code | Don't say |
|---|---|---|---|
| library exercise | An entry in the shared list everyone draws from, with equipment, movement pattern and muscles. | `exercises` | shared exercise, catalog |
| custom exercise | A person's own exercise name, linked to a library exercise or not. The app can call these "My exercises". | `user_exercises` | personal exercise |
| movement pattern | The kind of motion of a library exercise: squat, hip hinge, push, pull, lunge, carry, rotation. | `exercises.movement`; `movement_pattern` in the AI prompt | movement (alone) |
| skill practice | Training for a skill rather than load: calisthenics, rings, juggling, reaction drills, shadow boxing, stretching. | "movement-skill conventions" in `docs/extraction-conventions.md`; `test_movement_skill_conventions.py` | movement skill |

## Programs

| Term | Meaning | In code | Don't say |
|---|---|---|---|
| my program | A program that belongs to you: an ordered list of program workouts. | `programs`; `/programs` | |
| program template | A ready-made program you copy to make one of your own. | `/templates`; `/templates/{id}/copy`; `ProgramTemplate`; app label "Templates" | template (alone) |
| program workout | One workout in a program: its exercises, session warm-up and cool-down. Never a session you did. | `program_workouts`; `WorkoutOut`; `/workouts/{id}`; app label "Workout N" | workout (alone), plan, day |
| follow | Make a program the one the Train tab starts its next program workout from. | `POST /programs/{id}/follow` | |

## Progress and cost

| Term | Meaning | In code | Don't say |
|---|---|---|---|
| pinned lift | An exercise you pinned on the Progress tab to track its estimated max. | `users.key_lifts`; `/progress/lifts`; `PUT /me/key-lifts`; app label "Key Lifts" | key lift |
| AI call log | One row per paid model call: model, step, tokens, cost. | `ai_call_logs` | `llm_calls`, LLM call |
| AI usage | Your AI call count and cost for the month. | `GET /me/ai-usage`; `AiUsage` | AI spend, AI cost |

## Where the app's labels differ

The app still says "Key Lifts" (pinned lifts) and "This workout session is empty" (session). Changing
those labels is a visual change, so it waits for its own proposal.
