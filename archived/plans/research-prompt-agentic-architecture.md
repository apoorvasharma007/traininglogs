# Research prompt: is deterministic pre-parsing compatible with an "agentic" extraction app?

Paste everything below this line into a fresh research session.

---

## Context

I'm building `traininglogs`: a personal training-log system. A user writes a workout in loose
natural language / semi-structured markdown (see example below). An LLM-based pipeline maps
that text to a strict Pydantic schema (exercises, sets, weight, reps, RPE, tags, modality,
movement pattern, notes, etc.), which then gets stored in a database and served to a dashboard.

The pipeline is explicitly "agentic" in intent: it was built as a multi-step LLM extraction
process (a splitter call that lists exercises, a shell call for session-level fields, one LLM
worker call per exercise) specifically so it could handle *irregular*, free-form input —
calisthenics notation, timed holds, band-assisted reps, arbitrary phrasing — that a rigid parser
could never fully cover. That flexibility is the entire reason an LLM is in this pipeline at all;
a purely mechanical system was considered and rejected early on.

### Example input (one exercise block)

```
Incline DB Press
Warmup:
1. 15kg x 10
Sets:
1. 30kg x 8, RPE 7
2. 30kg x 8, RPE 7
3. 30kg x 7, RPE 8
Remarks:
last set felt heavy, elbow flare on rep 6
```

### The problem we found

On a live run against `openai/gpt-oss-120b` (Groq, free tier, `temperature=0`), asking the LLM
to extract an entire exercise block like the one above in one shot produced three distinct
value-level errors, all on textually clean, single-exercise, already-isolated input (no
surrounding noise, no ambiguity in the source text itself):

1. Weight dropped from all three working sets, and the entire warmup section dropped, despite
   reps and RPE for the same sets being extracted correctly.
2. An exercise-level RPE mentioned once in remarks ("RPE 6-7 overall") got attached to set 1
   instead of set 3, in direct violation of an explicit system-prompt rule to apply it to the
   *last* set.
3. Three working sets that were clearly under a `Sets:` header got filed into the `warmup_sets`
   field instead, leaving the real `sets` field empty.

All three outputs were schema-valid (so no validation retry fired) and none were flagged by our
existing deterministic drop-check, which only detects a value's total *absence* from the
session, not its *misplacement* onto the wrong field/exercise.

### The proposed fix we're now unsure about

We have a fully deterministic line-parser already, `DeepTrainingParser` (`parser/parse.py`),
built originally for a separate, more strictly-formatted markdown ingestion path. It correctly
parses lines shaped like `1. 80kg x 8`, partial reps, unilateral notation, and RPE, 100% of the
time, with zero LLM involvement. Two competing proposals surfaced:

**Proposal A ("reconcile after"):** Keep asking the LLM to extract everything, including the
numeric spine, every time. After the LLM call returns, run the deterministic parser over the
same isolated text; wherever the parser succeeds (returns a fully-parsed block) and disagrees
with the LLM's output, silently overwrite the LLM's value and log a warning. If the parser fails
(irregular format), leave the LLM's own output untouched.

**Proposal B ("parse first, ask second"):** Run the deterministic parser *before* the LLM call.
If it succeeds, never ask the LLM to reproduce the numeric spine at all — hand it the already-
parsed sets/weights/reps as given context and narrow its job to only what needs judgment
(exercise name/tags/modality/movement pattern, and per-set notes keyed to the set numbers it was
just given). If the parser fails (irregular format), fall back to asking the LLM to extract the
full block itself, exactly as today.

I proposed B as the "better" fix, reasoning it removes the reconciliation/arbitration logic
entirely by deciding field ownership before the call instead of after it. The response I got
back was: **"why build an agentic app then?"** — the concern being that if a deterministic
parser is silently making the real extraction decisions for the common case, and the LLM is
reduced to filling in labels around it, we may have quietly built a rule-based system with an
LLM sticker on it, not an agentic one — regardless of which of A or B we pick.

## What I actually want researched

This is not "which of A or B is more correct" — I think both of us agree B is more correct than
A on pure reliability grounds. The open question is architectural and philosophical as much as
technical:

1. **Is there a real, meaningful distinction between "agentic" and "deterministic pipeline with
   an LLM step," and does it matter for a system like this?** Or is "agentic" doing rhetorical
   work here that isn't actually load-bearing — i.e., is a hybrid deterministic+LLM extraction
   pipeline still legitimately called agentic in the way the term is used by serious
   practitioners (Anthropic, OpenAI, LangChain/LangGraph, Guardrails, Instructor, production
   RAG/extraction teams), or does it not deserve the label at all?

2. **Is there a third architecture that is more genuinely agentic than either A or B** — e.g.,
   exposing the deterministic parser to the model *as a callable tool*, and letting the model
   itself decide, per exercise, whether to invoke it, inspect its output, accept it, or override
   it with a stated reason? That would put the *decision* of "is this block regular enough to
   trust the parser" inside the agent's own reasoning rather than in our Python control flow —
   which may be the actual thing "agentic" is supposed to mean, and which neither A nor B does
   today (both hard-code the branch in our code, not the model's own choice).

3. **How do real production extraction systems that deal with semi-structured source text**
   (invoices, resumes, financial statements, medical forms, etc.) actually draw this line
   between deterministic and model-driven extraction? Is deterministic-parser-does-the-numbers,
   LLM-does-the-judgment the industry-standard shape for these systems, or do serious "agentic"
   systems in this space do something closer to option 2 (tool-calling loop with model-driven
   verification/self-correction) even at higher cost/latency?

4. **Self-verification / self-correction as an alternative to external reconciliation:** instead
   of a Python reconciler or a pre-parse gate, could the *same* LLM (or a cheap second pass) be
   given its own draft extraction plus the source text and asked to verify/correct itself against
   the source, the way agentic coding tools do a "check your work" pass? Is that a credible,
   evidence-backed reliability technique for this class of error (value dropped/misplaced despite
   correct schema), or does research suggest self-verification doesn't reliably catch a model's
   own extraction mistakes on the same source it just misread?

5. **Given we are constrained to free-tier models only** (currently Groq, `openai/gpt-oss-120b`
   and `llama-3.3-70b-versatile`; no paid APIs, no local model infra), which of these
   architectures are actually *practical* at that tier, and which assume capabilities (longer
   context reliability, native tool-use loops, high-effort reasoning modes) that free-tier models
   don't reliably deliver? Be concrete about what's realistic here versus what only works with
   frontier paid models.

6. **What would you recommend, and why** — not as an average of "some of each," but a real
   position: should this system keep the deterministic parser as an invisible pre/post-processing
   detail (A or B), promote it to a tool the agent explicitly chooses to use (option 2), lean into
   self-verification, or is the honest answer that we're overthinking a fundamentally solved
   problem and one of A/B is simply fine and "agentic" is not a design goal that should override
   reliability for a personal training-log app?

## Explicitly NOT in scope

- Re-litigating whether the deterministic parser (`DeepTrainingParser`) itself is correct — it's
  already tested and used in production for a separate ingestion path.
- The already-fixed chunk-leak/anchor-position bug from an earlier investigation — unrelated,
  already resolved.
- Token cost / prompt caching — a separate, lower-priority workstream.
- Switching to a paid model or local inference — free-tier only, no exceptions.

## What I want back

A direct recommendation with reasoning, not a survey of options with no conclusion. If the
answer is "you're overthinking this, ship B, agentic is not the right axis to optimize for
a training-log app," say that plainly. If the answer is "no, option 2 (model-driven tool use) is
what actually deserves the word agentic and is worth the added complexity, here's why," say that
instead, and be concrete about what it would look like for *this* system specifically (one
exercise block, one parser function, one LLM call) rather than in the abstract.
