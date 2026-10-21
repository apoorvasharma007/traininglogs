# AI workflow plan

## Goal

Set up the repo so a Claude run can fix bugs and do maintenance overnight, and Apoorva reviews the
resulting pull requests in the morning. Quality comes from a failing test first, CI as the witness,
and GitHub settings that stop the runner from pushing or merging. Feature work comes later.

## Decisions (agreed 2026-10-21)

| Area | Decision |
|---|---|
| Scope | Bug fixes and maintenance. Features later. |
| Runner | The claude.ai project, through the GitHub MCP, on the subscription (not an API key). |
| Intake | Notion is the inbox. GitHub issues labelled `ready` are the only task source. |
| Method | Bug: write a failing test first and read its failure message. Dependency bump, dead code, CI: existing suite stays green. Docs, CSS: before and after in the PR. Untestable: the PR says why. |
| Tests | CI's throwaway Postgres service (same as `ci.yml`). Never the staging database: `tests/signed_in.py` truncates every table. |
| Limits | Token scoped to this repo. Rulesets on `dev` and `main`: PR + CI green, 0 required approvals. The token can't edit `.github/workflows/` or secrets. Apoorva merges by hand. |
| PR shape | One PR per issue, `claude/<issue>-<slug>` into `dev`, merge commit. Trial cap 1 a night for two weeks while usage is measured, then raise. |
| Stuck | 2 CI attempts, then label `needs-human`, comment what was tried, next issue. Same for: no reproducing test, ambiguous issue, schema/UI/infra/prod DB/secrets. |
| Deploy | Merge into `dev` deploys staging after CI, so changes can be tested on a phone. Prod is untouched. |
| Morning report | Each run ends with one summary: PRs opened, issues parked and why. |

## Blast radius

Docs and settings only: `CLAUDE.md`, `.claude/`, `docs/architecture.md`, `docs/risk-map.md`,
`docs/`, plan files, GitHub repo settings, GitHub issues. No source code. Do not touch
`exercises/library-*` (five branches, in flight) or PR #36 (stale, see below).

## Steps

- [ ] 1. GitHub settings: rulesets on `dev` and `main`, scope the token (about 15 min, no repo change).
- [ ] 2. Context audit PR into `dev` from a `claude/` branch, docs only (sub-branch `chore/ai-workflow-2-audit`):
  - Read `CLAUDE.md`, `docs/`, `db-redesign-plan.md`, `react-plan.md`, `audit-bugs.md`, `CHANGELOG.md`.
    List contradictions with each other and with the code. Known: Python "3.12" vs "3.10 or newer" in `CLAUDE.md`.
  - Keep `CLAUDE.md` under 200 lines (178 now). Cut what the code already says. Move partial-scope rules into
    `.claude/rules/` with `paths:`. Turn `.claude/db-migration.md` and `.claude/testing-guide.md` into rules or skills.
    No `@imports`. Write rules as checkable do-statements with a reason; at most one or two emphasised lines.
  - Verify every file, path and command named exists. Ground each rule in a real past mistake (`audit-bugs.md`, git history).
  - Write `docs/architecture.md` (one page: modules, data flow, where the schema lives) and `docs/risk-map.md` (weak or untested areas, fragile spots, ranked).
  - Add the overnight rules from the Decisions table, and an `/overnight` skill and a `/verify` skill.
  - Run the full suite once against a private test database and report the result as it is.
  - Stop after opening the PR. Do not merge. The PR description lists what contradicted what and what could not be verified.
- [ ] 3. Triage: close the 9 stale 2025 issues (#2 to #13), file the `audit-bugs.md` backlog as issues
  (open: #1 disabled users, #2 pool of 10, 10 unverified candidates as "reproduce first"), label one `ready`.
- [ ] 4. First supervised night on one issue. Measure subscription usage. Review the PR together.
- [ ] 5. Raise the cap to 3 PRs a night once usage is known.

## Later (parked)

- Feature planning workflow (plans reviewed before building), hooks beyond GitHub rulesets, the picker redesign,
  a separate bot account or GitHub App for the runner.

## Open items

- Confirm the GitHub MCP exposes check-run results (and `workflow_dispatch` if wanted).
- PR #36 (`codebase-cleanup-2-3-4-comments-walkthrough`, 2026-10-08, targets `main`, conflicting, none of its
  3 commits in `dev`): treated as stale. Check `ux-audit.md` once for findings worth keeping, then close it with
  a note. Closing needs Apoorva's yes.
- The exercise-library chain (`exercises/library`, `-2-data`, `-3-schema`, `-4-own`, `-7-picker`) is a separate
  thread. Its memory is `exercise-library-plan.md`. It waits until this plan is through step 2.

## ▶ Resume here

2026-10-21: plan written on `chore/ai-workflow` (cut from `dev` at `8c9b454`), not pushed. Nothing built.
Next action: step 1, set the rulesets on `dev` and `main` in GitHub settings (about 15 minutes), then start a fresh
session and ask it to do step 2 from this file.
