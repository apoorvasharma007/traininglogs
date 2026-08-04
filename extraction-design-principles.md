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
