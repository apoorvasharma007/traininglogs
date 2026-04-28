from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: traininglogs <command> [options]")
        print()
        print("Commands:")
        print("  log    Process training logs, commit, and optionally publish dashboard")
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    cmd = sys.argv[1]
    sys.argv = [f"traininglogs {cmd}"] + sys.argv[2:]

    if cmd == "log":
        from traininglogs.cli.log import main as _main
        raise SystemExit(_main())
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'traininglogs --help' for usage.")
        sys.exit(1)
