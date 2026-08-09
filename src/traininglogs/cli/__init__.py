from __future__ import annotations

import sys

_HELP = """\
Usage: traininglogs <command> [options]

Commands:
  validate <file>     Parse and validate a training log — no DB write, no git.
                      Use this to smoke-test parsing (AI or rules) safely.

                      Options:
                        --parser ai|rules   Parser backend (default: ai)

  log <target>        Parse, insert into DB, and commit. Full pipeline.
                      <target> is a .md file, a directory of .md files,
                      or use --program/--phase/--week to resolve a week dir.

                      Options:
                        --program NAME      Program name (requires --phase, --week)
                        --phase N           Phase number
                        --week N            Week number
                        --parser ai|rules   Parser backend (default: ai)
                        --no-commit         Insert to DB but skip git commit
                        --message MSG       Custom commit message
                        --pr                Open a pull request after committing

Decision guide:
  Want to test parsing without touching the DB?  →  traininglogs validate
  Want to insert but not commit yet?             →  traininglogs log --no-commit
  Ready to commit and ship?                      →  traininglogs log
"""


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(_HELP)
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    cmd = sys.argv[1]
    sys.argv = [f"traininglogs {cmd}"] + sys.argv[2:]

    if cmd == "log":
        from traininglogs.cli.log import main as _main
        raise SystemExit(_main())
    elif cmd == "validate":
        from traininglogs.cli.validate import main as _main
        raise SystemExit(_main())
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'traininglogs --help' for usage.")
        sys.exit(1)
