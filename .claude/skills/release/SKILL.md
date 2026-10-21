---
name: release
description: Release what's on dev to production - bump the version, move the changelog entries, merge dev into main, and check the deploy. Use only when Apoorva asks for a release.
disable-model-invocation: true
---

# Release

Every step that pushes or merges needs Apoorva's yes in this session.

1. On `dev`, CI is green and staging works (`/verify`, step 5 against staging).
   Run `/doctor prompt-audit` and fix any stale or contradicting instruction it reports.
2. Cut `chore/release-<version>` from `dev`. Pick the version by semantic versioning: a breaking
   change to the API or stored data is major, a feature is minor, fixes only is patch.
3. On that branch:
   - set `version` in `pyproject.toml`;
   - in `CHANGELOG.md`, move the `[Unreleased]` entries under `## [<version>] - <YYYY-MM-DD>`,
     leave an empty `## [Unreleased]`, and update the compare links at the bottom.
   Commit `chore: release <version>`, open a PR into `dev`, merge it with a merge commit.
4. Open a PR from `dev` into `main` titled `Release <version>: <the main changes>`. Apoorva merges
   it with a merge commit, never a squash.
5. CI on `main` then tags `v<version>`, creates the GitHub release (notes generated from the merged
   PRs), and pushes a bot commit that sets the version in `docs/design.html`. The deploy waits for
   Apoorva's approval in the `prod` GitHub environment.
6. After the deploy, run `/verify` step 5 on production.
7. Merge `main` back into `dev`, so `dev` has the bot's `design.html` commit. Why: without it, the
   next release conflicts on that file, as it once did (`2b47e0d`).
