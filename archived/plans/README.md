# Archived plans

Superseded by [`roadmap.md`](../../roadmap.md) at the repo root, which is the single forward
plan. Kept because each records *why* a decision was made, and several of those reasons are
still load-bearing — but none of them describe outstanding work.

| File | State |
|---|---|
| `orchestration-refactor-plan.md` | Complete. Split the single extraction call into splitter → shell → one worker per exercise. Every step closed with a disposition. |
| `extraction-accuracy-plan.md` | Complete, and partly **reversed** — the deterministic parse-first path it introduced fired on 0 of 10 real exercises and was deleted 2026-08-03. |
| `refactor-data-model.md` | Complete. v3.0.0 flat `WorkingSet`, tags/modality/movement_pattern, warmup/cooldown tables. |
| `movement-skill-plan.md` | Complete as written, but see the caveat below. |
| `pre-online-plan.md` | Superseded by `roadmap.md`'s phases. |
| `research-brief-orchestration.md` | Research input, not a plan. |
| `research-prompt-agentic-architecture.md` | Research input, not a plan. Its question was answered: pre-parsing was removed. |

**Caveat on `movement-skill-plan.md`.** It shipped its conventions into `SYSTEM_PROMPT`, which
was deleted on 2026-08-09 with the monolithic parser. Six of its eight rules are not in the live
prompts and are therefore **not being applied** — they stopped taking effect when the split path
became the default, not when the constant was removed. The conventions are preserved verbatim in
[`docs/extraction-conventions.md`](../../docs/extraction-conventions.md). Deferred by decision
2026-08-09.

Still live at the repo root, and not archived:

- `roadmap.md` — the forward plan.
- `extraction-design-principles.md` — reference findings, still cited by the schema and prompt
  design.
