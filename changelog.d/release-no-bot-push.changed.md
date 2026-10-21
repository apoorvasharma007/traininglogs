A release no longer pushes a commit to `main` to stamp the version in `docs/design.html`,
which the `main` ruleset refused. The release PR sets that version, and a test checks it matches
`pyproject.toml`. Merging `main` back into `dev` after a release is no longer needed.
