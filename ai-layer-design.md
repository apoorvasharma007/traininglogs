> Parked 2026-10-28 (Apoorva): AI is out of Release A and the release plans for now. It comes back
> as app-wide voice logging during a workout (hold to speak a set, like Liftly), designed then.
> This doc measured the AI layer as it was on 2026-10-27 and is the starting point.

# Matching AI-read exercises to the library

Status: discussion draft, 2026-10-27. Read-only investigation of `exercises/library-f1-foundation`.
Nothing in the repo changed. No paid calls were made. Numbers marked "measured" come from the
local production copy `traininglogs_prod_copy_0002` and the F1 test database `traininglogs_f1`,
read with SELECT only.

## The short answer

You are right that this needs a proper design and more than a prompt edit. You are right that the
AI should propose the exercise, so the person only checks it. The part I'd push back on is the
MCP server and the open-ended orchestrated loop. Matching a name against 161 library exercises
plus your custom exercises is a lookup with a small judgment step on top. It isn't a job where the
model has to decide what to do next. Build it as one new step in the pipeline you already have.
Write the search once, as a plain Python function, and the loop and the MCP server can both reuse
it later without a rewrite.

## 1. How a note becomes a session today

The phone sends the note to `POST /inputs` (`src/traininglogs/api/app.py:405`). The server saves
the note first, then runs `extract()` (`src/traininglogs/ingest/extract.py:19`), which calls
`assemble()` (`src/traininglogs/agent/extraction.py:340`). Every model call goes to Anthropic's
`claude-haiku-4-5-20251001` (`src/traininglogs/agent/providers.py:12`). A Groq provider with
`llama-3.3-70b-versatile` exists (`providers.py:13`, `providers.py:407`), but only the eval scripts
use it. The app always builds `AnthropicProvider()` (`app.py:418`).

A note costs 2 + N model calls, where N is the number of exercises.

| Step | Call | Sends | Gets back |
|---|---|---|---|
| 1 | `split_exercises` (`extraction.py:37`) | the whole note and `SPLITTER_SYSTEM_PROMPT` (`prompts.py:5`) | the main exercises in order: position, name, and an anchor line copied from the note |
| 2 | `extract_session_shell` (`extraction.py:57`) | the whole note and `SHELL_SYSTEM_PROMPT` (`prompts.py:27`) | date, program, phase, week, focus, duration, session warm-up and cool-down, notes |
| 3..N+2 | `extract_exercise` (`extraction.py:77`), once per exercise | only that exercise's slice of the note, cut out with Python using the anchors (`extraction.py:185`), and `WORKER_SYSTEM_PROMPT` (`prompts.py:61`) | the exercise's name as written, its sets and warm-up sets as copied text, notes |

Each call already uses tool use. "Tool use" (OpenAI calls it function calling) means you describe a
function to the model with a JSON schema, and the model answers by filling in that function's
arguments instead of writing prose. Today's code forces one tool per call
(`tool_choice` at `providers.py:312`), so the tool works as a form to fill in, not an action the
model chooses. That difference matters below.

Python does everything that has to be exact. It turns rep text like "8+1" into counts
(`agent/reps.py`). It checks that each set's quoted source line is really in the note
(`extraction.py:260`) and that sets are numbered 1..n (`extraction.py:283`). It flags an RPE in
the text that no set picked up (`extraction.py:306`). A failed call is re-asked with the error up
to 2 more times (`providers.py:14`). A worker that still fails becomes a flagged placeholder
instead of a crash (`extraction.py:398`).

The result is saved as a confirmation card with status `pending` (`extract.py:59`). Every call is
written to `ai_call_logs` whether it worked or not (`extract.py:50`). The table stores step,
model, attempts, tokens, `cost_usd`, time and the raw payload
(`db/migrations/0001_baseline.sql:173`). Cost is tokens times the price table at `providers.py:19`
($1 per million input tokens, $5 per million output for Haiku 4.5).

The person then checks the confirmation card. A manual edit (`app.py:544`) uses no AI. An AI fix
(`app.py:497`) is one more call, `edit_extraction` (`agent/llm_extract_validator.py:12`), that
returns field edits. Confirm (`app.py:470`) builds a session from the AI extraction
(`ingest/confirm.py:32`) and saves it (`db/insert.py:166`).

**What a note costs (measured).** The local production copy has 17 notes read on 2026-10-02.

| | Value |
|---|---|
| Calls per note | 4.7 on average (2.9 exercise calls) |
| Tokens per note | about 15,000 in, 1,000 out |
| Cost per note | $0.020 average, $0.019 median, $0.040 highest |
| All 17 notes | $0.34 |
| Per step | splitter $0.002, session call $0.003, each exercise call $0.005 |

The exercise calls are most of the cost, about 4,200 input tokens each, mostly the worker prompt.
There are no AI fix rows in that copy, so I have no measured cost for those.

**Why confirm returns 422 now.** F1's foundation rule says every saved exercise points at a
library exercise or a custom exercise by id. `insert_session` looks up each exercise's id before
writing anything (`db/insert.py:181`). `exercise_names` refuses an exercise with neither id
(`db/insert.py:138`), and the API turns that refusal into 422 (`app.py:179`). The AI extraction
carries names only. The `Exercise` model already has `library_exercise_id` and
`custom_exercise_id` (`models/models.py:394`), so the ids have somewhere to go. Nothing fills them.
One more detail matters for the design. Once an id is set, the saved session takes the library's
name for it, not the note's wording (`db/insert.py:181`, comment above the call).

## 2. How well plain matching would do on your own notes (measured)

Before choosing a design I checked how far exact matching gets. I compared the names in your 17
AI extractions (50 exercises, 19 different names) and all saved sessions (1,077 exercises, 102
names) against the 161 library names and their 638 other names in `traininglogs_f1`. Comparison
ignores case and extra spaces, like `name_key` (`db/insert.py:125`).

| Names compared | Exact library name | Library name or an other name |
|---|---|---|
| AI-read names, 50 | 0 | 42 (84%) |
| Saved session names, 1,077 | 14 | 1,062 (98.6%) |

The AI-read names that matched nothing were "shoulder press" (3), "calf raise" (3), "press" (1),
and "forearm - 12.5 kg wrist flexion curl, 7.5 kg wrist extension curl" (1). The first two have
several library candidates, which is a real choice. The last one is two exercises read as one,
which is a reading mistake that no matching fixes.

Two things follow. Exact library names alone are useless, because people don't write "Overhead
Press (Barbell)". Other names do most of the work. Once M1 turns your old names into custom
exercises linked to library ones, your own past wording becomes an exact match too.

One catch. The library file says other names are "search words only, never used to link"
(`db/exercise_library.yaml`, header). That rule was about silent links. Here the match would be a
suggestion the person sees and confirms, but it is still your rule to bend (question 1). No other
name currently appears on two exercises (measured), though the file allows it.

## 3. The options

**(a) Plain matching first, the model only for leftovers.** After `assemble()`, a Python step
looks up each exercise's written name in this order. First your custom exercises, including ones
linked to the library. Then library names. Then other names. Anything left over goes to one model
call per note. That call gets each leftover name with its line from the note and the list of
exercise names, and returns a choice or "none". With 161 exercises the whole name list is about
4,100 characters, roughly 1,000 tokens (estimate, at about 4 characters per token), so v1 needs
no server-side search at all.

- Cost. Nothing for a note where everything matches. For a note with leftovers, about $0.001 to
  $0.003 more (estimate). On your notes, most would need no call.
- Speed. The lookup is a few milliseconds. The leftover call adds about one exercise call's time.
- Testing. The Python step is ordinary code with ordinary pytest tests. The model step can be
  scored against your history for free, because M1 gives every old session the right id. That
  answer key already exists.
- Weakness. The order is fixed. If a new kind of reasoning is needed later, you add a step by hand.

**(b) The model calls tools in a loop inside the server.** An "agent loop" means you give the
model several tools, such as `search_library(query)` and `list_my_custom_exercises()`. You let it
call any of them, run what it asked for, send the results back, and repeat until it answers. The
model decides the steps. Your backend still runs every tool, so nothing leaves the server.

- Cost. Each round sends the whole conversation again: system prompt, tool descriptions, earlier
  results. Used only for matching, I'd guess $0.004 to $0.008 more per note, 20 to 40% on top of
  today. If the loop replaced the whole pipeline, so the model read the note and decided its own
  steps, my guess is 1.5 to 3 times today's cost. These are guesses, and a dry run against
  `eval_arms.py` would settle them.
- Accuracy. The current pipeline got its accuracy from fixed steps the model can't skip: anchors,
  per-exercise slices, source-line checks (`extraction.py:349`). A loop gives the model the choice
  to skip them.
- Code. `AnthropicProvider.extract` handles one forced tool call (`providers.py:273`). A loop needs
  a second method that lets the model choose a tool, runs it, and continues. That's about 60 to
  100 lines plus tests (estimate). It also needs a cap on rounds so a confused model can't spend
  money in circles.
- Where it earns its place. When the steps really aren't known ahead, like "find me a substitute
  for this exercise that uses the same muscles and equipment I have". Matching one name is not
  that.

**(c) An MCP server.** MCP (Model Context Protocol) is an open standard from Anthropic for
connecting AI apps you don't control to your tools and data. You run a small server that lists
tools, such as `search_exercises` and `log_session`. Any MCP client, like the Claude app, Claude
Code or Cursor, can then let its model call them. MCP is a cable standard between someone else's
AI app and your code. It doesn't make the model smarter, and it doesn't add tools the Anthropic API
lacks. Inside your own backend, where your code already calls the model API, an MCP server is an
extra process with its own login, deploy and failure modes. It carries the same tool calls that
(b) makes with a Python function call.

MCP earns its place when the model runs outside your app. One real example for you is Alfred.
Saying "log today's session" to Claude on your phone, with Claude calling traininglogs to save it,
is exactly what MCP is for. That is a separate feature, a new way in for notes. It doesn't fit
this job. Parking it costs nothing, because the tools it would expose are the same Python
functions (a) and (b) need.

**(d) Considered and set aside.** Asking each exercise call to pick the id would put the name list
into every exercise call, about 3 times the extra tokens of (a). It would also mix reading with
matching, against the "one job per call" finding in `extraction-design-principles.md`. Putting the
list in the splitter is cheaper, but the splitter prompt would then differ per person. That changes
what `PROMPT_VERSION` (`prompts.py:172`) means, and it mixes two jobs in one call.

| | (a) Matching + leftover call | (b) Tool loop in server | (c) MCP server |
|---|---|---|---|
| Extra cost per note | $0 to $0.003 (estimate) | $0.004 to $0.008 for matching only (guess) | same as (b), plus hosting |
| New code | one Python step, one small call | (a)'s search plus a loop in the provider | (b) plus a server, auth, deploy |
| Testable for free | yes, against M1's ids | partly, needs recorded runs | as (b) |
| Fits one user now, more later | yes. New users' wording is what the leftover call is for | yes, at higher cost | only for clients outside the app |
| Grows into | (b) and (c) by reusing the search function | (c) | |

## 4. How the person confirms, corrects, or adds a custom exercise

Whatever finds the match, the confirmation card is still where the person decides. Your rule that
anything changing saved data is confirmed applies here, and so does the foundation rule.

- **Exact match on your own name or a library name.** The card shows the library exercise's
  name, since that's what will be saved, with your wording under it ("you wrote: squats"). No
  check needed.
- **Other-name match or model match.** Same display, but it counts as one of the "things to
  check". The card already has this mechanism. Paths in `uncertain_fields` are counted into
  `checks` (`frontend/src/screens/review/Review.tsx:176`), and Confirm asks "Things Still to Check"
  first (`Review.tsx:366`). The match step adds `exercises.N.exercise` to `uncertain_fields` and
  the card counts it. No new concept is needed.
- **Correcting.** Tapping the exercise name opens the F2 picker, already filled with the written
  name. Today, tapping it opens a free-text rename (`Review.tsx:245`). That changes to the picker,
  because a typed name can't be saved any more.
- **Nothing fits.** No id is set and the card shows "Pick an exercise". The picker's "+ Custom"
  makes a custom exercise (`POST /exercises`, `app.py:264`) and the card uses its id. Confirm is
  blocked until every exercise has an id, because the server would refuse it anyway. F1's approved
  rule is that saving never creates a custom exercise, so I'd keep creation as an explicit tap,
  not something confirm does quietly (question 2).
- **Learning from picks.** When you pick "Overhead Press (Barbell)" for "shoulder press", the app
  could keep "shoulder press" as your name for it, a custom exercise linked to the library. Next
  time that name is an exact match at no AI cost. This is what makes matching get better on its
  own (question 3).

Two places in the code need care. An AI fix or a manual edit can rename an exercise
(`agent/card_edits.py`, `llm_extract_validator.py:88`), and the id would then be stale. Running the
free Python match again after every edit fixes that. Pending confirmation cards saved before this
change have no ids, so `GET /extractions/{id}` (`app.py:443`) can run the same free match when it
finds them.

## 5. Recommendation: (a), shipped in two small steps

**Step 1, no AI.** Add `match_exercises(conn, user_id, extract)`. It runs after `assemble()` in
`ingest/extract.py`, fills `library_exercise_id` or `custom_exercise_id` on each exercise, and adds
other-name matches to `uncertain_fields`. Wire the review card's exercise name to the picker and
block confirm while any exercise has no id. This alone removes the 422. On your measured notes it
pre-fills 42 of 50 exercises. It belongs in Release A, because confirming notes is broken until
something like it ships.

**Step 2, the leftover call.** One call, `match_leftover_exercises`, made only when step 1 leaves
names unmatched. It sends the leftover names with their note lines and the name list, and asks for
a choice or "none". Its answers always count as things to check. Before any paid run, score it on
Groq's free tier against M1's answer key, then do a `--dry-run` for the Haiku cost, per CLAUDE.md
"Money".

Growing later without a rewrite depends on one choice in step 1. Write the lookup as a plain
function, `search_exercises(conn, user_id, query) -> list[ExerciseHit]`, separate from
`match_exercises`. Then:

- When the library grows past what fits in a prompt (plan step 10 adds about 870
  free-exercise-db exercises, `exercise-library-plan.md:401`), step 2 sends the top hits from
  `search_exercises` instead of the whole list. Nothing else changes.
- If a job ever needs a real loop, `search_exercises` becomes the first tool. The only new piece
  is the loop method in the provider.
- If Alfred or the Claude app should log sessions, an MCP server exposes `search_exercises` and the
  existing save path as tools. It's a thin wrapper over functions that already have tests.

One caution about the search. The phone already has one, MiniSearch with typo tolerance
(`frontend/src/lib/exerciseSearch.ts:20`). Step 1 needs only exact matching, so it doesn't
duplicate that. A fuzzy server search would be a second search that can drift from the phone's.
Build it only when step 2 or the library size needs it.

Principles that shaped this. Redesign from first principles changed the question from "how do we
bolt matching onto prompts" to "if ids had been required from day one, where does matching go".
The answer is a step between reading and the confirmation card. Laziness protocol cut the server
search, the loop and the MCP server from v1, since measured exact matching already covers 84%.
Foundational thinking put the data shape first. The ids go on the `Exercise` fields that already
exist, and uncertainty uses the existing `uncertain_fields`, so no new card concept is needed.
Experience first keeps the person to one tap per uncertain exercise, rather than picking every
exercise by hand as the plan's F1.4 had it.

## 6. Questions only you can answer

1. Can an other-name match be pre-filled as a suggestion to check, even though other names "never
   link"? My default is yes, because the person still confirms it.
2. When nothing fits, does confirm stay blocked until the person picks or taps "+ Custom", or does
   confirm create custom exercises for the leftovers? My default is blocked, which keeps F1's
   approved "saving never creates one".
3. Should a pick remember your wording ("shoulder press" becomes your name for Overhead Press
   (Barbell)), so next time it matches for free? My default is yes, done on confirm and shown on
   the card in one line, with no extra prompt.
4. Does step 1 ship inside Release A, with step 2 right after? My default is yes, because step 1
   is what un-breaks confirming notes, and step 2's value is easier to judge once step 1's
   leftovers are counted on real notes.
5. Is logging by talking to Claude, through Alfred or the Claude app, something you want in the
   next 90 days? My default is no. MCP is parked in the plan's later list, ready to wrap
   `search_exercises` when you want it.

## Discussion log

- 2026-10-27. First draft. Waiting on answers to section 6.
