from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
WEBSITE_ROOT = PROJECT_ROOT.parent / "website"
INPUTS_DIR = PROJECT_ROOT / "inputs"


def _rebuild_dashboard(dry_run: bool) -> None:
    print("\n[rebuilding dashboard...]")
    if dry_run:
        print("[DRY-RUN] Would rebuild dashboard")
        return
    from traininglogs.cli.dashboard import main as dashboard_main
    try:
        dashboard_main()
        print("✓ Dashboard updated")
    except Exception as e:
        print(f"⚠  Dashboard build failed: {e}")


def _publish_dashboard(dry_run: bool) -> None:
    print("\n[publishing dashboard to website...]")
    dashboard_file = WEBSITE_ROOT / "static" / "training-almanac" / "index.html"

    if dry_run:
        print("[DRY-RUN] Would commit and push dashboard to website repo")
        return

    if not WEBSITE_ROOT.exists():
        print(f"⊘ Website repo not found at {WEBSITE_ROOT}, skipping publish")
        return

    if not dashboard_file.exists():
        print("⊘ Dashboard HTML not found in website repo, skipping publish")
        return

    cmds = [
        (["git", "add", str(dashboard_file)], "stage"),
        (["git", "diff", "--cached", "--quiet"], "check"),
        (["git", "commit", "-m", "chore: update training dashboard"], "commit"),
        (["git", "push"], "push"),
    ]

    for cmd, label in cmds:
        ret, _, stderr = _run(cmd, cwd=WEBSITE_ROOT)
        if label == "check" and ret == 0:
            print("⊘ Dashboard unchanged, nothing to publish")
            return
        if label != "check" and ret != 0:
            print(f"⚠  Website publish failed at '{label}': {stderr}")
            return

    print("✓ Dashboard published — GitHub Actions will deploy it shortly")


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _get_changed_files() -> list[str]:
    _, stdout, _ = _run(["git", "status", "--porcelain"])
    return [line[3:].split("\t")[0] for line in stdout.strip().split("\n") if line]


def _current_branch() -> Optional[str]:
    _, stdout, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return stdout.strip() if stdout.strip() != "HEAD" else None


def _ensure_feature_branch() -> bool:
    branch = _current_branch()
    if branch in ("main", "master"):
        print("⚠  You're on 'main'. You should work on a feature branch.")
        response = input("Create a feature branch? (y/n): ").strip().lower()
        if response != "y":
            print("Aborting. Please create a feature branch and try again.")
            return False
        branch_name = input("Enter branch name: ").strip()
        ret, _, stderr = _run(["git", "checkout", "-b", branch_name])
        if ret != 0:
            print(f"✗ Failed to create branch: {stderr}")
            return False
        print(f"✓ Created and checked out branch: {branch_name}")
        return True
    print(f"✓ On feature branch: {branch}")
    return True


def _resolve_targets(
    target: Optional[str],
    program: Optional[str],
    phase: Optional[int],
    week: Optional[int],
) -> list[Path]:
    if target:
        p = Path(target)
        if p.is_file():
            return [p]
        if p.is_dir():
            files = sorted(p.glob("*.md"))
            if not files:
                print(f"✗ No .md files found in {p}")
                sys.exit(1)
            return files
        print(f"✗ {target} is not a file or directory")
        sys.exit(1)

    if program:
        if phase is None or week is None:
            print("✗ --program requires --phase and --week")
            sys.exit(1)
        slug = program.lower().replace(" ", "_")
        target_dir = INPUTS_DIR / "programs" / slug / f"phase_{phase}" / f"week_{week}"
        if not target_dir.exists():
            print(f"✗ Directory not found: {target_dir}")
            sys.exit(1)
        files = sorted(target_dir.glob("*.md"))
        if not files:
            print(f"✗ No .md files found in {target_dir}")
            sys.exit(1)
        return files

    print("✗ Provide a target file/directory or --program --phase --week")
    sys.exit(1)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="traininglogs log",
        description="Process training logs, commit changes, and optionally publish dashboard.",
    )
    parser.add_argument("target", nargs="?", help="Path to a .md file or directory of .md files")
    parser.add_argument("--program", help="Program name (with --phase and --week)")
    parser.add_argument("--phase", type=int, help="Phase number (used with --program)")
    parser.add_argument("--week", type=int, help="Week number (used with --program)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    parser.add_argument("--no-commit", action="store_true", help="Skip git commit step")
    parser.add_argument("--pr", action="store_true", help="Create a pull request after committing")
    parser.add_argument("--message", default="", help="Custom commit message")
    parser.add_argument("--publish", action="store_true", help="Push updated dashboard to website")

    args = parser.parse_args(argv)

    md_files = _resolve_targets(args.target, args.program, args.phase, args.week)

    print("=" * 60)
    print("TRAINING LOG WORKFLOW")
    print("=" * 60)

    if not args.dry_run and not _ensure_feature_branch():
        return 1

    print(f"\n[1] Found {len(md_files)} file(s) to process")
    for f in md_files:
        print(f"  {f}")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "\n✗ DATABASE_URL is not set.\n"
            "Start Postgres with 'docker compose up -d' and set DATABASE_URL in .env"
        )
        return 1

    print("\n[2] Running parser...")
    if args.dry_run:
        print(f"[DRY-RUN] Would process {len(md_files)} file(s)")
        return 0

    from dotenv import load_dotenv
    load_dotenv()

    from traininglogs.db.db import get_connection, apply_schema
    from traininglogs.processor.processor_v2 import process_md_file

    conn = get_connection()
    apply_schema(conn)
    try:
        for md_path in md_files:
            process_md_file(md_path, conn)
    except SystemExit as e:
        print(str(e))
        return 1
    finally:
        conn.close()

    print("✓ Parser completed")

    if args.no_commit:
        print("\n[3] Skipping git commit (--no-commit)")
        _rebuild_dashboard(args.dry_run)
        if args.publish:
            _publish_dashboard(args.dry_run)
        return 0

    print("\n[3] Staging and committing changes...")

    ret, _, stderr = _run(["git", "add", "-A"])
    if ret != 0:
        print(f"✗ Failed to stage files: {stderr}")
        return ret

    ret, _, _ = _run(["git", "diff", "--cached", "--quiet"])
    if ret == 0:
        print("⊘ No changes to commit")
        return 0

    msg = args.message or f"feat: log training session(s) — {', '.join(f.stem for f in md_files)}"
    ret, _, stderr = _run(["git", "commit", "-m", msg])
    if ret != 0:
        print(f"✗ Failed to commit: {stderr}")
        return ret

    print(f"✓ Committed: '{msg}'")

    if args.pr:
        print("\n[4] Creating pull request...")
        ret, _, _ = _run(["gh", "--version"])
        if ret != 0:
            print("⚠  GitHub CLI (gh) not installed. Skipping PR creation.")
        else:
            ret, _, stderr = _run(["gh", "pr", "create", "--fill", "--title", msg, "--body", msg])
            if ret != 0:
                print(f"⚠  Could not create PR: {stderr}")
            else:
                print("✓ Pull request created!")
    else:
        print("\n[4] Skipped PR creation (use --pr to enable)")

    _rebuild_dashboard(args.dry_run)

    if args.publish:
        _publish_dashboard(args.dry_run)
    else:
        print("\n[5] Skipped website publish (pass --publish to deploy)")

    print("\n" + "=" * 60)
    print("✓ WORKFLOW COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
