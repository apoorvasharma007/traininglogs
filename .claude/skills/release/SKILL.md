---
name: release
description: Release what's on dev to production - bump the version, gather the changelog fragments, merge dev into main, and check the deploy. Use only when Apoorva asks for a release.
disable-model-invocation: true
---

# Release

Every step that pushes or merges needs Apoorva's yes in this session.

1. On `dev`, CI is green and staging works (`/verify`, step 5 against staging).
   Run `/doctor prompt-audit` and fix any stale or contradicting instruction it reports.
2. Cut `chore/release-<version>` from `dev`. Pick the version by semantic versioning: a breaking
   change to the API or stored data is major, a feature is minor, fixes only is patch.
3. On that branch:
   - set `version` in `pyproject.toml`, and the same version in `docs/design.html`'s
     `<span class="app-version">` (a test fails CI when they differ);
   - run `.venv/bin/python scripts/changelog.py --release <version>`: it writes the fragments in
     `changelog.d/` under `## [<version>] - <today>` in `CHANGELOG.md`, updates the compare links
     and deletes the fragments. Read the new section before committing.
   Commit `chore: release <version>`, open a PR into `dev`, merge it with a merge commit.
4. Open a PR from `dev` into `main` titled `Release <version>: <the main changes>`. Apoorva merges
   it with a merge commit, never a squash.
5. CI on `main` then tags `v<version>` and creates the GitHub release (notes generated from the
   merged PRs). The deploy waits for Apoorva's approval in the `prod` GitHub environment.
6. After the deploy, run `/verify` step 5 on production.
