# Documentation overhaul

## Goal

Several documents describe a system that no longer exists (two local servers, markdown-first
logging, "the API never writes", Fly). Apoorva asked for a full rewrite in plain language, following
the unslop rules: facts checked against the code, one job per document, no em dashes, no padding,
mechanisms and numbers instead of adjectives. Each document is designed with Apoorva first (its
job and outline), then written, then approved before it is committed.

## Scope

Rewritten:

| Group | Files |
|---|---|
| For anyone reading the repo | `README.md`, `docs/design.html`, `infra/README.md`, `web/README.md`, `scripts/README.md`, `tests/fixtures/README.md`, `web/sample_inputs.md` |
| Working guides (for Apoorva and coding agents) | `CLAUDE.md`, `.claude/db-migration.md`, `.claude/testing-guide.md`, `.claude/regen-historical.md`, `.claude/migration-plan.md`, `docs/migration-runbook.md`, `docs/extraction-conventions.md`, `extraction-design-principles.md` |

Records, left as they are except for outright factual errors: `CHANGELOG.md`, `roadmap.md`,
`historical-review/`, `archived/`.

## Process per document

1. Check every claim against the code; ask when something can't be confirmed.
2. Agree the document's one job and its outline with Apoorva.
3. Write it.
4. Apoorva approves the content; commit on `docs/overhaul-N-<file>`, squash into
   `docs/overhaul`.

## Steps

- [x] 1. `README.md`: what the app does and why, nothing else (setup and CLI moved out, Apoorva 2026-10-03)
- [x] 2. `docs/design.html`: rewritten outside-in (what it is, web app, flow, repeat, AI, data, API, where it runs, limits, next); no markdown/CLI; approved 2026-10-03
- [x] 3. `infra/README.md`, `web/README.md`, `web/sample_inputs.md`: rewritten; samples 1 to 6 kept verbatim, a run and a skills sample added; approved 2026-10-03
- [x] 4. `scripts/README.md`, `tests/fixtures/README.md`: rewritten; 12 retired scripts, `test_import.py` and `fixtures/invalid/` deleted; CLI and parser removal added to the roadmap as a non-urgent enhancement; approved 2026-10-03
- [x] 5. `CLAUDE.md`: rewritten as working rules (money and data rules, local development, branching and releases, testing, docs); approved 2026-10-03
- [x] 6. Guides: `.claude/db-migration.md` and `.claude/testing-guide.md` rewritten as short plain steps; `migration-plan.md`, `regen-historical.md`, `migration-runbook.md` moved to `archived/guides/`; CLAUDE.md guide table updated; approved 2026-10-03
- [ ] 7. `docs/extraction-conventions.md`, `extraction-design-principles.md`
- [ ] 8. Merge `docs/overhaul` into `dev`

## ▶ Resume here

Step 7, `docs/extraction-conventions.md` and `extraction-design-principles.md`: agreeing their jobs, then step 8 merges into dev. Branch `docs/overhaul` from `dev`.
