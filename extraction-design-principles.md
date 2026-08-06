# What actually makes LLM extraction accurate

Reference notes, gathered 2026-08-04. These are findings from production extraction teams and
published research, not opinions formed here. They are recorded because they contradicted our own
assumptions — we believed prompt wording was the main lever and the data model was fixed. Both
were wrong.

Read this before changing a prompt or a schema.

---

## The findings

| # | Finding | Source |
|---|---|---|
| 1 | Renaming one field from `final_choice` to `answer` moved accuracy from **4.5% to 95%**. The model uses field names as search hints — a field called `po_number` gets matched against "PO Number" and "Purchase Order #" in the document. | [Instructor](https://python.useinstructor.com/blog/2024/09/26/bad-schemas-could-break-your-llm-structured-outputs/) |
| 2 | **55% of all changes that improved extraction accuracy were structural flattening** — denormalising a schema "so the model never had to infer a relationship." | [Reducto](https://docs.reducto.ai/extraction/best-practices-extract) |
| 3 | Deeply nested schemas (**4+ levels**) and wide schemas (**50+ fields**) both degrade quality. The model must hold more state while generating, and constraint pressure compounds through nesting. | Reducto |
| 4 | **34% of improvements came from better field descriptions** that made a field's scope explicit. | Reducto |
| 5 | Marking a field **required when the data might be absent forces the model to hallucinate** a value. Use optional/nullable wherever a value may not exist. | Instructor |
| 6 | Few-shot examples improve accuracy by **up to 17%**, and **1–4 well-chosen examples** is often the sweet spot — more is not reliably better. | [multiple](https://learnprompting.org/docs/basics/few_shot) |
| 7 | Breaking extraction into smaller focused calls helps once a schema exceeds roughly **8–10 fields** or has complex interdependencies. | [Structured-output reliability research](https://arxiv.org/html/2605.02363v1) |
| 8 | **Source grounding** — every extracted value carries its location in the source — is the standard way to detect fabrication. Anything that cannot be located in the source text was invented. | [google/langextract](https://github.com/google/langextract) |
| 9 | Chained LLM stages propagate errors: a subtly wrong intermediate "passes through intact, and every downstream agent treats it as fact." Prefer decomposing by **subject** over decomposing by **stage**. | [Error-cascade research](https://arxiv.org/abs/2603.04474v1) |
| 10 | Intrinsic self-correction (a model checking its own work with no external signal) is **not** reliable and often degrades results. Self-correction works when there is an external verifier. | [Huang et al., ICLR 2024](https://arxiv.org/abs/2310.01798) |

---

## What they mean for this codebase

**The schema is a bigger lever than the prompt.** Findings 1–5 are all schema properties. Our own
prompt carries three rules that exist only to explain schema decisions:

```
- rep_count: ALWAYS an object {full: N, partial: M} — never a bare number
- warmup_sets: rep_count here is a plain integer, NOT an object
- unilateral sets: use unilateral_rep_count with left/right instead of rep_count
```

The third rule is the Wrist Flexion defect. `rep_count` (2 levels) and `unilateral_rep_count`
(4 levels) are two competing fields for one concept, so the model must infer which relationship
applies — exactly what finding 2 says to remove. **The schema manufactured that failure. No prompt
wording reliably undoes it.**

**The extraction schema does not have to be the database schema.** `ExerciseExtract` currently
inherits from `Exercise`, the production model behind the `exercises` and `working_sets` tables.
That single line of coupling forces the model to fill a shape designed for storage and querying.
Splitting them gives each a shape suited to its job, with a projection function in between — and
gets the accuracy win with no migration, no API change, and no dashboard change.

**Fewer fields is better, so deferring a feature genuinely helps accuracy.** Finding 3 means
dropping `tags`, `modality`, `movement_pattern`, `rep_tempo`, `target_muscle_groups`,
`current_goal` and `form_cues` from the extraction schema does not merely postpone work — it
improves accuracy on the fields that remain.

**Synonyms are not a prompt problem.** Teaching a prompt that "DB press" means "dumbbell press"
is unbounded, brittle, and breaks grounding (finding 8) — the model would write a name absent from
the source. Extract the name verbatim, then canonicalise in a separate lookup step. A data problem
with a data solution: auditable, fixable without touching prompts, testable for free.

**"100% accuracy" is the wrong target.** The achievable and more useful target is *100% of errors
caught before they reach the database* — which is what the confirmation card plus the source-line
checks provide. An error caught costs two seconds; an error missed corrupts history.

---

## Rules of thumb we are adopting

1. **Before writing a prompt rule, ask whether the schema can remove the need for it.** A rule
   explaining a schema decision is a smell.
2. **Name fields the way the source text names them.** Field names are search hints (finding 1).
3. **Flat beats nested.** If the model has to infer a relationship, flatten it and rebuild the
   relationship in Python (finding 2).
4. **Optional unless genuinely always present** (finding 5).
5. **Describe every field's scope** in the schema, not in the prompt (finding 4).
6. **2–4 examples, drawn from real inputs**, not invented ones (finding 6).
7. **A check encodes a property of the data, never a memory of a bug.** (Our own rule; see
   `roadmap.md` § Conventions.)

---

## An open hypothesis worth testing

If schema complexity is the real bottleneck, then **a weaker model should improve most when the
schema is simplified.** `openai/gpt-oss-120b` currently scores far below Haiku 4.5 — 3 of 10 sets
carried a source line, versus 102 of 102 — and it dropped 4 and 3 sets on two fixtures.

Groq is free. So each schema change can be measured on Groq at **$0.00** before spending anything
on Haiku. If Groq's accuracy climbs materially, that is strong evidence the schema was the
constraint, and it may make a free model viable for this app.

This is the cheapest experiment available and it is recorded here so it does not get forgotten.

---

## Learning from corrections — the direction this app should grow in

A fixed prompt cannot serve every user. Someone logging powerlifting, someone logging rings and
juggling, and someone logging running intervals need different guidance, and no single prompt is
optimal for all three. Writing a prompt per vertical means writing, maintaining, and choosing
between them — which does not scale and gets stale.

**The better answer moves specialisation out of the prompt and into the examples.**

### Dynamic few-shot selection

Rather than fixing the examples in the prompt, retrieve them per request: embed the incoming text,
find the most similar previously-confirmed extractions, and inject the top 1–3 as examples.

The evidence is good. Retrieval-augmented few-shot prompting *"consistently outperforms both
random prompting and retrieval-based labeling"*, with reported F1 gains of 11–12% over static
prompting on named-entity benchmarks. The mechanics are unremarkable: embed the request, query an
index of curated examples, rank by similarity, insert the best few.

Sources: [RAG-based dynamic prompting for few-shot NER](https://arxiv.org/abs/2508.06504) ·
[Structured dynamic prompting with RAG](https://www.nature.com/articles/s44387-025-00062-2)

### Why this app is unusually well placed

The published bottleneck for these systems is blunt: **"high-quality, reliable feedback is the
bottleneck."** Most teams have no ground truth, so they fall back on model-generated feedback —
which [the self-correction survey](https://arxiv.org/html/2406.01297v3) shows does not reliably
work.

**This app has a human confirming every extraction.** The confirmation card is not only a safety
net; it is a ground-truth generator, produced for free as a side effect of the product working
the way it already does. That is the expensive part of this pattern, and it is already built.

### The loop

```
raw text -> extraction -> human confirms or corrects -> stored
                                  |
                a verified (input -> output) pair in THIS user's notation
                                  |
              retrieved as an example next time similar text arrives
```

Every table it needs is already in the Phase 2 plan: `raw_inputs` (the text), `extractions.extract`
(what the model produced), `corrections` (what the human changed), `status = confirmed` (which
pairs are trustworthy). **No new data model is required** — which is a good sign the layering was
right.

### Three cautions

1. **Do not build it before there is data.** Retrieval needs a corpus of confirmed extractions.
   Phase 2 produces that corpus; building retrieval first is premature.
2. **Bad examples poison the pool.** The literature is explicit about cleaning it regularly and
   dropping noisy or ambiguous entries. A confirmed-but-wrong extraction teaches the wrong thing,
   so there must be a way to exclude one.
3. **Static examples become the floor, not dead weight.** A new user has no history, and retrieval
   sometimes finds nothing similar. The hand-written examples are the cold-start set and the
   fallback — they stay.

### What this replaces

Per-vertical prompts, a growing pile of notation conventions in the system prompt, and the
temptation to enumerate every synonym a user might type. All three are attempts to anticipate
users in advance. Retrieval learns them instead.
