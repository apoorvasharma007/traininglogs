# changelog.d

Unreleased changes, one file per pull request that changes behaviour. At release,
`scripts/changelog.py --release <version>` gathers them into `CHANGELOG.md` and deletes them.

- Name: `<issue>.<section>.md`, for example `63.fixed.md`. Without an issue, a short name in
  lowercase with dashes: `docs-only-deploy.changed.md`.
- Section: `added`, `changed`, `fixed` or `removed`.
- Content: the entry as it should read in the changelog, wrapped at 100 characters.

`.venv/bin/python scripts/changelog.py` shows what the next release would say.
`tests/test_changelog.py` fails CI on a badly named or empty fragment.
