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

- [x] 1. GitHub settings: rulesets on `dev` and `main` (2026-10-21; a direct push to `dev` was rejected). Token scoping skipped on purpose, see Open items.
- [x] 2. Context engineering, built together (reworked 2026-10-21). Docs and config only, sub-branch
  `chore/ai-workflow-2-audit`, one commit per sub-step, then squash, ask before push, PR to `dev`, don't merge.
  Each sub-step: Claude explains and proposes, Apoorva decides, then Claude writes. Nothing inherited by default.
  - [x] 2a. How Claude reads context (see Notes), and the contradiction audit (see Findings).
  - [x] 2b. Glossary (ubiquitous language): one word per concept, code name beside it. `docs/glossary.md`. No code renames.
  - [x] 2c. `CLAUDE.md` from a blank page, one rule at a time: what it prevents, kept only on a yes. 20 rules
    decided; `CLAUDE.md` 123 -> 74 lines. Until 2d lands, the path rules below exist only here.
  - [x] 2d. Nine path rules in `.claude/rules/`; skills `/setup` (was `.claude/local-development.md`), `/verify`
    (was `.claude/testing-guide.md`), `/release`, `/traininglogs-agent`. `.claude/db-migration.md` folded into
    `rules/schema.md` and `CLAUDE.md`. Changelog reason in `CLAUDE.md` corrected (release notes come from PRs).
  - [x] 2e. `docs/architecture.md` and `docs/risk-map.md` (12 risks, ranked). Suite baseline taken early for it:
    Python 748 passed, 0 failed, 0 skipped, 96% coverage; frontend 144 tests, flaky locally.
    Found: CI on `dev` red since 2026-10-13 (unhandled `QuotaExceededError` from `session.test.tsx:161`), which
    blocks every merge into `dev` under the rulesets.
  - [x] 2f. Changelog line, squashed into `chore/ai-workflow`. PR #46 into `dev`, open, not merged.
- [ ] 3. Triage (the CI failure on `dev` was fixed by hand in PR #47, merged 2026-10-21). Close the 9 stale 2025 issues (#2 to #13), file the `audit-bugs.md` backlog as issues
  (open: #1 disabled users, #2 pool of 10, 10 unverified candidates as "reproduce first"), label one `ready`.
- [ ] 4. First supervised night on one issue. Measure subscription usage. Review the PR together.
- [ ] 5. Raise the cap to 3 PRs a night once usage is known.

## Later (parked)

- Feature planning workflow (plans reviewed before building), hooks beyond GitHub rulesets, the picker redesign,
  a separate bot account or GitHub App for the runner.
- Rethink the testing strategy and setup (built as the easiest next step for the POC). 2f only records a baseline.
- A reusable ubiquitous-language skill in `~/.claude/skills`, from what worked in 2b.
- When code is next refactored, bring its names in line with `docs/glossary.md` (tables, fields, routes,
  components) and the app labels ("Key Lifts", "workout session"). Each rename needs its own approval.
- Blog post on context engineering, from the Notes below.
- Enforce instead of describe: ruff + mypy in CI (Python style), a CI check that fails on glossary "don't say"
  words in docs, commit-message lint.

## Step 2 notes (for the blog)

How context loads, checked against code.claude.com/docs/en/memory and /skills on 2026-10-21:

| Piece | When it enters context | Cost |
|---|---|---|
| `CLAUDE.md` (repo root and parents) | Every session, in full, at launch | Always. Docs: target under 200 lines; longer lowers adherence |
| `CLAUDE.md` in a subdirectory | When Claude first reads or edits a file in that folder | Only there |
| `.claude/rules/x.md` without `paths:` | At launch, like `CLAUDE.md` | Always |
| `.claude/rules/x.md` with `paths:` globs | When Claude reads or edits a matching file | Only when relevant |
| `@path` import | At launch, inlined | Same as pasting it in; organises, saves nothing |
| Skill `.claude/skills/<n>/SKILL.md` | Name + description at launch; body when `/n` is typed or Claude judges it relevant | Small until used; body stays once loaded |
| Auto memory `MEMORY.md` | First 200 lines / 25KB every session | Always |

- Everything above is context, not enforcement. To block an action for certain, use a hook or a permission
  rule (or, for the runner, GitHub rulesets).
- Contradictions: "if two instructions contradict each other, Claude may pick one arbitrarily."
- Write checkable instructions: "Run `npm test` before committing", not "Test your changes".
- Built-in check: `/doctor prompt-audit` reports stale paths and contradictions across `CLAUDE.md`, rules and skills.
- The claude.ai project sees none of this. Project skills don't load in "cloud threads in a project"; it reads
  repo files only when told to, through the GitHub connection.

## Step 2 findings (2a audit, 2026-10-21, on `dev` at `8c9b454`)

| # | Where | Says | Truth |
|---|---|---|---|
| 1 | `CLAUDE.md:107` | Python 3.10 or newer | 3.12 in `.python-version`, Dockerfile, CI; `pyproject.toml` says `>=3.10` |
| 2 | `CLAUDE.md` Testing, `testing-guide.md:26` | A request without the API key gets 401 | Auth is a Supabase sign-in pass (`api/auth.py`); no API key in `src/` |
| 3 | `README.md:19-21`, `design.html` (lines 183, 185, 451, 510) | Single user, API key in Settings, `X-Api-Key` header, accounts later | Accounts shipped in 5.0.0. Also wrong on `origin/main` |
| 4 | `design.html` | "Thirteen tables" | 16 in `schema.sql` |
| 5 | `CLAUDE.md` money rules | `llm_calls` table | The table is `ai_call_logs` |
| 6 | `CLAUDE.md:11` | `exercise-library-plan.md` as the example plan | Only on `exercises/library*` branches, not on `dev` |
| 7 | `testing-guide.md:20-22` | `web/sample_inputs.md`, "Repeat a past session" | `web/` was replaced by `frontend/`; repeat call deleted |
| 8 | `testing-guide.md:6` | Tests on the shared 5433 DB | roadmap 2026-10-13: shared DB has library schema, use a private DB on `dev` |
| 9 | ci.yml:31, `infra/modules/app/cloud_run.tf:89` | `API_KEY` still set | Leftover; the tf comment says the next release removes it. Code, not docs: out of scope, note in risk map |
| 10 | this plan | `CLAUDE.md` 178 lines | 123 |
| 11 | local `main` | 4.1.0 | 39 commits behind `origin/main` (5.0.0). Local only, not a doc problem |

Paths in `db-redesign-plan.md` and `react-plan.md` that no longer exist (`web/`, `ingest/repeat.py`) are
history: those plans describe deleting them. Not contradictions.

## Open items

- Known gap, accepted for now: the claude.ai GitHub connection has full access. The runner could merge its own
  PRs or edit the rulesets. Only the prompt rule "never merge, never touch settings" stops it. Fix later with a
  separate bot account or a GitHub App with narrow permissions. Check every PR the runner opens for a self-merge.
  Also confirm `protect-main` shows Active.

- Confirm the GitHub MCP exposes check-run results (and `workflow_dispatch` if wanted).
- PR #36 (`codebase-cleanup-2-3-4-comments-walkthrough`, 2026-10-08, targets `main`, conflicting, none of its
  3 commits in `dev`): treated as stale. Check `ux-audit.md` once for findings worth keeping, then close it with
  a note. Closing needs Apoorva's yes.
- The exercise-library chain (`exercises/library`, `-2-data`, `-3-schema`, `-4-own`, `-7-picker`) is a separate
  thread. Its memory is `exercise-library-plan.md`. It waits until this plan is through step 2.

## Runner setup (for Apoorva)

Paste into the claude.ai project's instructions:

> Before any work on apoorvasharma007/traininglogs, read `.claude/skills/traininglogs-agent/SKILL.md` on
> `dev` through the GitHub connection and follow it.

## ▶ Resume here

2026-10-21: steps 1 and 2 done. PR #47 (CI fix) merged into `dev`. Step 2 is PR #46, `dev` merged into it, waiting
for green CI and Apoorva's merge.
Before the first run: paste the "Runner setup" line into the claude.ai project's instructions (after #46 is on `dev`).
Next action: step 3. Close #2 to #13 (on a yes), file the `audit-bugs.md` backlog, label one `ready`. About 30 minutes.
