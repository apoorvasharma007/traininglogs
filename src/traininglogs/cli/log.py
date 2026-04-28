from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
WEBSITE_ROOT = PROJECT_ROOT.parent / "website"
INPUT_LOGS_DIR = PROJECT_ROOT / "input_training_logs_md"
OUTPUT_LOGS_DIR = PROJECT_ROOT / "output_training_logs_json"
PROCESSOR_SCRIPT = PROJECT_ROOT / "src" / "traininglogs" / "processor" / "processor_v2.py"


def _rebuild_dashboard(dry_run: bool) -> None:
    print("\n[5/6] Rebuilding dashboard...")
    if dry_run:
        print("[DRY-RUN] Would rebuild dashboard")
        return
    from traininglogs.cli.dashboard import main as dashboard_main
    try:
        dashboard_main()
        print("✓ Dashboard updated")
    except Exception as e:
        print(f"⚠️  Dashboard build failed: {e}")


def _publish_dashboard(phase: int, week: int, dry_run: bool) -> None:
    print("\n[6/6] Publishing dashboard to website...")
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
        (["git", "commit", "-m", f"chore: update training dashboard phase {phase} week {week}"], "commit"),
        (["git", "push"], "push"),
    ]

    for cmd, label in cmds:
        ret, _, stderr = run_command(cmd, cwd=WEBSITE_ROOT)
        if label == "check" and ret == 0:
            print("⊘ Dashboard unchanged, nothing to publish")
            return
        if label != "check" and ret != 0:
            print(f"⚠️  Website publish failed at '{label}': {stderr}")
            return

    print("✓ Dashboard published — GitHub Actions will deploy it shortly")


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def get_changed_files() -> list[str]:
    _, stdout, _ = run_command(["git", "status", "--porcelain"])
    files = [line[3:].split("\t")[0] for line in stdout.strip().split("\n") if line]
    return files


def get_current_branch() -> Optional[str]:
    _, stdout, _ = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return stdout.strip() if stdout.strip() != "HEAD" else None


def ensure_feature_branch() -> bool:
    branch = get_current_branch()

    if branch in ("main", "master"):
        print("⚠️  You're on the 'main' branch. You should work on a feature branch.")
        print("\nExample: git checkout -b phase-3-week-5")
        response = input("\nCreate a feature branch? (y/n): ").strip().lower()
        if response != "y":
            print("Aborting. Please create a feature branch and try again.")
            return False

        branch_name = input("Enter branch name (e.g., phase-3-week-5): ").strip()
        ret, _, stderr = run_command(["git", "checkout", "-b", branch_name])
        if ret != 0:
            print(f"❌ Failed to create branch: {stderr}")
            return False

        print(f"✓ Created and checked out branch: {branch_name}")
        return True

    print(f"✓ On feature branch: {branch}")
    return True


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="traininglogs log",
        description="Process training logs, commit changes, and optionally publish dashboard.",
    )
    parser.add_argument("--phase", type=int, required=True, help="Phase number")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    parser.add_argument("--no-commit", action="store_true", help="Skip git commit step")
    parser.add_argument("--pr", action="store_true", help="Create a pull request after committing (requires gh CLI)")
    parser.add_argument("--message", default="", help="Custom commit message")
    parser.add_argument("--publish", action="store_true", help="Push updated dashboard to website (triggers GitHub Pages deploy)")

    args = parser.parse_args(argv)

    print("=" * 70)
    print("TRAINING LOG WORKFLOW")
    print("=" * 70)

    print("\n[0/6] Ensuring you're on a feature branch...")
    if not args.dry_run and not ensure_feature_branch():
        return 1

    phase = args.phase
    week = args.week

    print(f"\n[1/6] Checking for markdown files in phase {phase} week {week}...")
    target_dir = INPUT_LOGS_DIR / f"phase {phase} week {week}"
    md_files = list(target_dir.glob("*.md"))
    if not md_files:
        print(f"❌ No markdown files found in phase {phase} week {week}/")
        return 1
    print(f"✓ Found {len(md_files)} markdown file(s)")

    print("\n[2/6] Running JSON parser...")
    if args.dry_run:
        print(f"[DRY-RUN] Would run processor for phase {phase} week {week}")
        ret = 0
    else:
        ret, _, stderr = run_command([sys.executable, str(PROCESSOR_SCRIPT), "--phase", str(phase), "--week", str(week)])
        if ret != 0:
            print("❌ Parser failed!")
            print(stderr)
            return ret
        print("✓ Parser completed successfully")

    if args.no_commit:
        print("\n[3/6] Skipping git commit (--no-commit)")
        _rebuild_dashboard(args.dry_run)
        if args.publish:
            _publish_dashboard(phase, week, args.dry_run)
        return 0

    print("\n[3/6] Staging and committing changes...")

    if args.dry_run:
        changed = get_changed_files()
        if changed:
            print(f"[DRY-RUN] Would commit {len(changed)} file(s):")
            for f in changed:
                print(f"  - {f}")
        else:
            print("[DRY-RUN] No changes to commit")
        return 0

    ret, _, stderr = run_command(["git", "add", "-A"])
    if ret != 0:
        print(f"❌ Failed to stage files: {stderr}")
        return ret

    ret, _, _ = run_command(["git", "diff", "--cached", "--quiet"])
    if ret == 0:
        print("⊘ No changes to commit")
        return 0

    if not args.message:
        args.message = f"Sync training logs for phase {phase} week {week}"

    ret, _, stderr = run_command(["git", "commit", "-m", args.message])
    if ret != 0:
        print(f"❌ Failed to commit: {stderr}")
        return ret

    print(f"✓ Committed: '{args.message}'")

    if args.pr:
        print("\n[4/6] Creating pull request...")
        branch = get_current_branch()

        ret, _, _ = run_command(["gh", "--version"])
        if ret != 0:
            print("⚠️  GitHub CLI (gh) not installed. Skipping PR creation.")
            print("Install with: brew install gh")
        else:
            ret, _, stderr = run_command([
                "gh", "pr", "create",
                "--fill",
                "--title", args.message,
                "--body", f"Automated sync for {args.message}",
            ])
            if ret != 0:
                print(f"⚠️  Could not create PR: {stderr}")
                print("You can create it manually in GitHub")
            else:
                print("✓ Pull request created!")
    else:
        print("\n[4/6] Skipped PR creation (use --pr to enable)")

    _rebuild_dashboard(args.dry_run)

    if args.publish:
        _publish_dashboard(phase, week, args.dry_run)
    else:
        print("\n[6/6] Skipped website publish (pass --publish to deploy)")

    print("\n" + "=" * 70)
    print("✅ WORKFLOW COMPLETE")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
