#!/usr/bin/env python3
"""One-command workflow: Parse logs + commit + create PR.

After you manually copy files to input_training_logs_md/, run:
  python3 scripts/process_and_commit.py

This will:
1. Ensure you're on a feature branch (not main!)
2. Validate all markdown files parse correctly
3. Run the JSON parser
4. Stage and commit changes (both markdown + JSON)
5. Create a PR automatically (if --pr flag used)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

# -------------------------------------------------------------------
# Project paths
# -------------------------------------------------------------------
THIS_DIR = Path(__file__).parent
PROJECT_ROOT = THIS_DIR.parent
INPUT_LOGS_DIR = PROJECT_ROOT / "input_training_logs_md"
OUTPUT_LOGS_DIR = PROJECT_ROOT / "output_training_logs_json"
PROCESSOR_SCRIPT = PROJECT_ROOT / "processor" / "processor.py"


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a shell command and return exit code + stdout + stderr."""
    result = subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def get_changed_files() -> list[str]:
    """Get list of modified/new files in git."""
    _, stdout, _ = run_command(["git", "status", "--porcelain"])
    files = [line[3:].split("\t")[0] for line in stdout.strip().split("\n") if line]
    return files


def get_current_branch() -> Optional[str]:
    """Get current git branch name."""
    _, stdout, _ = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return stdout.strip() if stdout.strip() != "HEAD" else None


def ensure_feature_branch() -> bool:
    """Ensure we're on a feature branch (not main/master).
    
    If on main/master, prompt user to create/checkout a feature branch.
    Returns True if on feature branch, False if user declines.
    """
    branch = get_current_branch()
    
    if branch in ("main", "master"):
        print("⚠️  You're on the 'main' branch. You should work on a feature branch.")
        print("\nExample: git checkout -b phase-3-week-5")
        response = input("\nCreate a feature branch? (y/n): ").strip().lower()
        if response != "y":
            print("Aborting. Please create a feature branch and try again.")
            return False
        
        # Create branch name from input
        branch_name = input("Enter branch name (e.g., phase-3-week-5): ").strip()
        
        # Create and checkout branch
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
        prog="process_and_commit",
        description="Parse training logs, commit changes, and optionally create PR.",
    )
    
    parser.add_argument(
        "--phase",
        type=int,
        required=True,
        help="Phase number (required)",
    )
    parser.add_argument(
        "--week",
        type=int,
        required=True,
        help="Week number (required)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Skip git commit step",
    )
    parser.add_argument(
        "--pr",
        action="store_true",
        help="Create a pull request after committing (requires 'gh' CLI)",
    )
    parser.add_argument(
        "--message",
        default="",
        help="Custom commit message (auto-generated if not provided)",
    )
    
    args = parser.parse_args(argv)
    
    print("=" * 70)
    print("TRAINING LOG WORKFLOW")
    print("=" * 70)
    
    # Step 0: Check branch
    print("\n[0/4] Ensuring you're on a feature branch...")
    if not args.dry_run and not ensure_feature_branch():
        return 1
    
    phase = args.phase
    week = args.week
    
    # Step 1: Validate input files exist
    print(f"\n[1/4] Checking for markdown files in phase {phase} week {week}...")
    target_dir = INPUT_LOGS_DIR / f"phase {phase} week {week}"
    md_files = list(target_dir.glob("*.md"))
    if not md_files:
        print(f"❌ No markdown files found in phase {phase} week {week}/")
        return 1
    print(f"✓ Found {len(md_files)} markdown file(s)")
    
    # Step 2: Run parser
    print("\n[2/4] Running JSON parser...")
    if args.dry_run:
        print(f"[DRY-RUN] Would run: python3 processor/processor.py --phase {phase} --week {week}")
        ret = 0
    else:
        ret, stdout, stderr = run_command([sys.executable, str(PROCESSOR_SCRIPT), "--phase", str(phase), "--week", str(week)])
        if ret != 0:
            print("❌ Parser failed!")
            print(stderr)
            return ret
        print("✓ Parser completed successfully")
    
    # Step 3: Git commit
    if args.no_commit:
        print("\n[3/4] Skipping git commit (--no-commit)")
        return 0
    
    print("\n[3/4] Staging and committing changes...")
    
    if args.dry_run:
        changed = get_changed_files()
        if changed:
            print(f"[DRY-RUN] Would commit {len(changed)} file(s):")
            for f in changed:
                print(f"  - {f}")
        else:
            print("[DRY-RUN] No changes to commit")
        return 0
    
    # Stage changes
    ret, _, stderr = run_command(["git", "add", "-A"])
    if ret != 0:
        print(f"❌ Failed to stage files: {stderr}")
        return ret
    
    # Check for changes
    ret, stdout, _ = run_command(["git", "diff", "--cached", "--quiet"])
    if ret == 0:
        print("⊘ No changes to commit")
        return 0
    
    # Create commit message
    if not args.message:
        args.message = f"Sync training logs for phase {phase} week {week}"
    
    ret, _, stderr = run_command(["git", "commit", "-m", args.message])
    if ret != 0:
        print(f"❌ Failed to commit: {stderr}")
        return ret
    
    print(f"✓ Committed: '{args.message}'")
    
    # Step 4: Create PR
    if args.pr:
        print("\n[4/4] Creating pull request...")
        branch = get_current_branch()
        
        if args.dry_run:
            print(f"[DRY-RUN] Would create PR for branch: {branch}")
            return 0
        
        # Check if gh CLI is available
        ret, _, _ = run_command(["gh", "--version"])
        if ret != 0:
            print("⚠️  GitHub CLI (gh) not installed. Skipping PR creation.")
            print("Install with: brew install gh")
            return 0
        
        ret, _, stderr = run_command([
            "gh", "pr", "create",
            "--fill",
            "--title", args.message,
            "--body", f"Automated sync for {args.message}",
        ])
        
        if ret != 0:
            print(f"⚠️  Could not create PR: {stderr}")
            print("You can create it manually in GitHub")
            return 0
        
        print("✓ Pull request created!")
    else:
        print("\n[4/4] Skipped PR creation (use --pr to enable)")
    
    print("\n" + "=" * 70)
    print("✅ WORKFLOW COMPLETE")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
