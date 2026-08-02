# Research brief: reliable LLM extraction from flexible, unstructured personal input

## What this is

I'm the sole developer/user of a personal training-log app called `traininglogs`. I've hit a
genuine architectural fork and want help thinking it through with broader research and fresh
perspective — not implementation, design thinking. Please treat this as a deep-research /
design-partner session: survey how real systems handle this tension, lay out the actual
option space with tradeoffs, and help me reason toward a direction. I'll make the final call
myself, but I want to see the full landscape first, including precedent I likely don't know
about.

## App context

`traininglogs` turns a workout written in a markdown/text file into a strict, validated,
queryable data structure (Pydantic model → PostgreSQL), then serves it to a personal
dashboard. One person, one user, real personal use (not a multi-tenant product — yet; a
mobile capture app is a possible future direction but not being built now).

There are two parsing paths:

1. **`--parser rules`**: a deterministic, regex/markdown-based parser. Requires a specific
   structure — `## Exercise N` headers, `**Name:**` fields, `### Working Sets` sections,
   fixed line formats like `1. 90kg x 8`. Fast, free, 100% predictable. Zero LLM involved.
2. **`--parser ai`** (the default, and the one this brief is about): an LLM call that takes
   *free-form personal writing* — however I naturally jot down a workout, in whatever shape
   feels natural that day — and maps it into the same strict schema. This path exists
   *specifically* to avoid forcing rigid structure on the input. That's the whole point of
   it: I should be able to write "did bench today, 90kg for a few sets, felt like an 8" and
   have it map correctly, without learning or enforcing a template.

Every extraction — regardless of path — goes through a human confirmation step (a rendered
card showing what was extracted; I either confirm or type a correction) before anything is
written to the database. Nothing is silently written unreviewed. This matters for the
discussion below: today's failure mode is "I have to manually fix one field," not silent data
corruption.

## The data model (schema shape, so you understand what has to be extracted)

```
TrainingSession
├── session-level fields: date, program, phase, week, focus, duration, notes
├── warmup[]        lightweight movements: name, reps?, duration?, notes?
├── exercises[]     the main work — this is where almost all the volume/complexity lives
│   └── Exercise
│       ├── name, tags[], modality, movement_pattern[]
│       ├── warmup_sets[]   this exercise's own ramp-up sets
│       └── sets[]          the working sets — the data that actually matters
│           └── WorkingSet: weight_kg?, rep_count{full,partial}?, rpe?, duration_seconds?,
│                            distance_meters?, heart_rate_bpm?, notes?, failure_technique?
└── cooldown[]      same shape as warmup
```

A session typically has 1–10 exercises. Real historical sessions go up to 10 exercises with
multiple sets and remarks each.

## The problem: monolithic single-call extraction is unreliable on longer sessions

Today, one LLM call gets the *entire* session — every exercise, every set, warmup, cooldown,
notes — as one deeply nested structured-output (tool-calling) request, in one shot.

I found a concrete, reproducible bug: on a real 6-exercise session (with a warmup block,
per-exercise remark blocks, and a cooldown block, all in loose prose — not the rigid
`## Exercise N` format), repeated identical calls to the model produced **materially
different results each time**. In two separate runs, the model completely and silently
dropped remark content (an RPE value stated once after a block of sets, and other qualitative
remarks) for the *last 3 of 6* exercises — no trace in any field, nothing flagged as
uncertain. Earlier exercises in the same call were extracted correctly.

I diagnosed this carefully before assuming a cause:
- Ruled out token-limit truncation: checked `finish_reason` on the raw API response — it was
  `tool_calls` (clean completion), not `length` (truncated). The JSON was well-formed and
  complete; the model simply chose not to populate those fields for later exercises.
- Hypothesized sampling-temperature non-determinism (neither provider pinned a temperature,
  so identical input was hitting each API's non-zero default). Pinned `temperature=0` on both
  providers as a fix.
- Re-tested after pinning temperature: the result was **not fixed, and in one run was worse**
  — that run had zero RPE values captured across *all six* exercises (both the earlier-working
  ones and the ones that failed before), while still keeping notes for the first three.

My conclusion from this evidence: this isn't primarily sampling randomness (temperature was
already addressed and didn't help). It looks like a **capacity/degradation effect from asking
one call to hold together too much structured output at once** — a long single generation's
quality dropping for content later in the output, independent of temperature. This is a
documented general phenomenon in long-generation structured output, not something specific to
one provider.

## The fix I was converging on before hitting the real tension

Standard practice for this class of problem (I looked into Anthropic's own published guidance
on agent/workflow patterns) is **decomposition**: instead of one big call, use an
**orchestrator-workers** pattern — one step figures out what the subtasks are (here: how many
exercises, and where each one's text begins/ends), then one smaller, focused call per subtask
(one call per exercise, against a much smaller schema), then deterministic code assembles the
results. Smaller focused calls should not suffer the same "degrades over a long generation"
problem, since no single call has to track more than one exercise's worth of detail.

This seemed like the right direction — until I got to the actual mechanics of the
orchestrator step.

## The real tension I want help thinking through

**Orchestrator-workers requires knowing the subtask boundaries (where each exercise starts
and ends in the raw text) before you can dispatch workers.** For rigidly structured input
(`## Exercise N` headers), this is free — plain-text segmentation, zero LLM cost, 100%
reliable. But for genuinely loose, free-form personal writing — the *entire reason the AI
parser path exists in the first place* — there may be no clean, regular marker at all. If I
build the orchestrator's segmentation step to expect *some* minimum structure in order to be
reliable, I'm quietly reintroducing the same rigidity the AI-parser path was built to escape.
If I make segmentation itself an open-ended LLM judgment call to preserve full flexibility, I
haven't obviously solved the reliability problem — I've just moved the "is this LLM call
reliable on messy input" question one level up, to a different (smaller, but still
LLM-based) call.

So: **how do you decompose a large LLM extraction task into smaller, more reliable
sub-calls, without requiring the user's input to already be rigidly, predictably
structured?** Is there a real middle ground, or is "flexible input" and "reliable
decomposed extraction" fundamentally in tension in a way I need to make a real trade-off on
rather than solve cleanly?

## What I want out of this research session

1. **Survey real precedent.** How do production systems that both (a) accept genuinely
   free-form/unstructured user input *and* (b) need reliable structured extraction internally
   actually handle this? Candidates worth looking at: AI-native note-taking apps (e.g. Notion
   AI, Mem, Reflect) that structure freeform notes; receipt/invoice extraction systems;
   customer-support ticket parsers; medical intake/transcription systems; journaling apps with
   AI-derived structure; any published engineering writeups on "semi-structured extraction at
   scale." What architecture do they actually use? Do any of them face this exact fork, and
   how did they resolve it (not just "add more prompt engineering")?
2. **Is there a robust, structure-agnostic segmentation technique** that's meaningfully more
   reliable than "ask an LLM to find the boundaries of a long messy document," without
   requiring the user to follow a rigid format? (E.g., techniques from document layout
   analysis, topic segmentation, or hybrid heuristic+LLM approaches that are more robust to
   looseness than either pure regex or pure open-ended LLM judgment.)
3. **Is a hybrid/adaptive approach the right framing** — e.g., detect at runtime whether the
   input is "structured enough" for free deterministic segmentation, and only fall back to an
   LLM-based (or even monolithic) path for genuinely loose input, rather than picking one
   universal strategy? If so, what's a reliable way to detect "structured enough" without
   itself becoming a brittle rule?
4. **Should the app instead lean on UX rather than pipeline cleverness** — e.g., gently guide
   the user toward *some* minimal, unobtrusive structural convention (not a rigid template,
   but something like "blank line + exercise name on its own line" as a soft convention) via
   the existing templates, so segmentation stays reliable and cheap without the user feeling
   forced into a form? Is this a cop-out, or is this actually how real systems resolve this
   tension in practice (meeting the user partway rather than solving pure NLP segmentation)?
5. **Given all of the above, what would you actually recommend**, concretely, for this
   specific schema and this specific scale (personal use, one user today, CLI-first, possible
   future mobile capture)? I'd like a menu of real options with honest tradeoffs, not a single
   prescriptive answer — I want to reason through it myself, but with the option space fully
   on the table including things I likely haven't thought of.

## Constraints / non-negotiables for any proposed design

- Must keep the human-confirmation-before-write step — no direction should require removing
  that safety net.
- Must not require the user to memorize or follow a rigid template as a hard requirement —
  soft/optional guidance is fine, a hard requirement defeats the purpose of the AI-parser path.
- Should not require training or fine-tuning a custom model — the strategic bet so far has
  been: build the durable IP (schema, validation, confirmation loop), keep the model itself a
  swappable commodity (currently Anthropic Claude Haiku and Groq/Llama as a free/local
  alternative for testing).
- Personal/solo scale — no need to optimize for throughput, concurrency at scale, or
  multi-tenant isolation. Latency of a few extra seconds per session is a total non-issue.
- Don't over-engineer for hypothetical future scale (a possible future mobile app) at the cost
  of unnecessary complexity today — but flag clearly if a direction would be wasted work once
  that future arrives, versus a direction that's forward-compatible with it.
