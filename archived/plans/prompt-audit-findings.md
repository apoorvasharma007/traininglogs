# Prompt audit findings: traininglogs config

Findings from a prompt audit of this repo's Claude Code configuration (`CLAUDE.md`,
`.claude/rules/`, `.claude/skills/`) run on 2026-10-21 against Opus 5.5. Apoorva agreed to fix
them. Findings about `~/.claude` files are handled in another session and are not listed here.

Line numbers are from the audit. `CLAUDE.md` was being edited at the time, so find each passage by
its quoted text, not its line number.

## Fixes to apply

### 1. The agent run's first step gets no CI run (high)

`.claude/skills/traininglogs-agent/SKILL.md`, "How to do one issue", step 2 and step 4.

The step says "Push it alone and read CI's failure message." CI runs only on pushes to `main` or
`dev` and on pull requests (`.github/workflows/ci.yml`, `on:` block). A push to a
`claude/<issue>-<slug>` branch with no PR gets no CI run, so there is no failure message to read.

Replace:

```
   - Bug: write a test that reproduces it. Push it alone and read CI's failure message. It must
     fail for the reason in the issue. Then push the fix and see CI pass.
```

with:

```
   - Bug: write a test that reproduces it. Push it alone and open a draft PR into `dev`: CI runs
     on pull requests, not on branch pushes. Read CI's failure message. It must fail for the
     reason in the issue. Then push the fix and see CI pass.
```

Replace:

```
4. Open a PR into `dev`. Title: `<type>: <what changed>`. Body: `Fixes #<issue>`, what was wrong,
   the test and its CI failure message, the fix, what you couldn't verify.
```

with:

```
4. Open the PR into `dev`, or mark the draft ready. Title: `<type>: <what changed>`. Body:
   `Fixes #<issue>`, what was wrong, the test and its CI failure message, the fix, what you
   couldn't verify.
```

Check: re-read `ci.yml`'s `on:` block. If someone has since added a push trigger for other
branches, this fix isn't needed.

### 2. History in the release skill (medium)

`.claude/skills/release/SKILL.md:9-10`. "5.0.0 went out this way (PRs #41 and #40)." records past
events, not a rule. Keep only the first sentence:

```
Every step that pushes or merges needs Apoorva's yes in this session.
```

### 3. History in the verify skill (medium)

`.claude/skills/verify/SKILL.md:8-9`. Delete this paragraph:

```
This is how changes are checked today. It was built as the quickest way to a working app, and its
redesign is parked in `ai-workflow-plan.md`.
```

It describes the file's history and points at a parked plan. `ai-workflow-plan.md` doesn't mention
a redesign of `/verify`, and the pointer invites a side trip.

## Decisions for Apoorva first

Ask Apoorva about each item below before editing. They are proposals, not agreed fixes.

### 4. `/verify` makes a paid call that `CLAUDE.md` restricts

`.claude/skills/verify/SKILL.md` step 4: "A confirmation card needs one AI extraction, a paid call
of a few cents: paste a note from `tests/fixtures/valid/`."

The `CLAUDE.md` Money section says "Before any paid model run, run it with `--dry-run`" and "Quote
costs from a dry run or from the `ai_call_logs` table, never from memory." The `/verify` step makes
a paid call with no dry run, and "a few cents" is a cost from memory. `~/.claude/CLAUDE.md` also
says to stop and ask before spending paid API budget.

Ask: does one test extraction during `/verify` need Apoorva's yes? Either way, replace "a few
cents" with a figure from `ai_call_logs`, such as the median cost of recent extractions.

### 5. The agent's park list omits `schemas.py`

`.claude/skills/traininglogs-agent/SKILL.md`, "Park the issue instead", parks a fix that touches
`src/traininglogs/agent/prompts.py`. `.claude/rules/prompts.md` covers both `prompts.py` and
`src/traininglogs/agent/schemas.py`, and says an edit to either makes every cached eval call a new
paid call. An unattended run could therefore edit `schemas.py`.

Ask: add `schemas.py` to the park list?

### 6. `CLAUDE.md` now names `docs/architecture.md` but doesn't say to keep it updated

The opening paragraph of `CLAUDE.md` now names `docs/architecture.md` (one page) beside
`docs/design.html`. The "Words and docs" section still says "If the flow, the data model, the API
or the hosting changes, update `docs/design.html` in the same PR", so `architecture.md` can go
stale.

Ask: should that rule name both files?

## Outside the config, noticed in passing

- The compare links at the bottom of `CHANGELOG.md` stop at `[3.1.0]`, though 4.0.0, 4.1.0 and
  5.0.0 are released. `/release` step 3 covers this for future releases. The three missing links
  are a one-time fix.
- `db-redesign-plan.md` is still in the repo root. Its last `▶ Resume here` entry is dated
  2026-10-06. If the plan is finished, `CLAUDE.md` says it moves to `archived/plans/`. If it moves,
  update the reference in `.claude/rules/schema.md` ("A new table follows `db-redesign-plan.md`").

## Already checked, no change needed

Every path the config names exists. Every command and flag it names is defined in the repo:
`--dry-run` in `scripts/eval_arms.py`, `clean_test_data` and its TRUNCATE in `tests/signed_in.py`,
the `ai_call_logs` ON DELETE CASCADE, `status = 'rejected'`, the `strict: true` rule (backed by
`tests/test_agent_no_strict_tool_use.py`), Python 3.12 in `.python-version`, the Dockerfile and CI,
the four npm scripts, `pip-compile` (from `pip-tools`), `db_test` on port 5433, the Terraform output
`service_url`, the date lines at the top and bottom of `docs/design.html`, and the isolation guard
test. The agent run's pushes and the rules scoped to paths are deliberate overrides of the
user-level rules, not conflicts.

## ▶ Resume here

Done 2026-10-21. Fixes 1 to 3 applied. Decisions: 4, ask before the paid extraction, no cost figure; 5, `schemas.py`
added to the park list; 6, the rule names both docs. "Noticed in passing" needed no change: the `CHANGELOG.md`
compare links already include 4.0.0, 4.1.0 and 5.0.0, and `roadmap.md` keeps `db-redesign-plan.md` in the root on
purpose.
