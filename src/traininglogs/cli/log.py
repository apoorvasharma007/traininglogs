from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"


def _rebuild_dashboard() -> None:
    print("\n[rebuilding dashboard...]")
    from traininglogs.cli.dashboard import main as dashboard_main
    try:
        dashboard_main()
        print("✓ Dashboard updated")
    except Exception as e:
        print(f"⚠  Dashboard build failed: {e}")


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
        p = Path(target).resolve()
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


_UNSET = object()


def _process_ai_file(md_path: Path, conn, provider=None, orchestrator=None, output_dir=_UNSET):
    """capture -> extract -> confirm, driven straight from the ingest/ module.

    This is the only place the interactive confirm loop runs -- deliberately not inside
    ingest/extract.py, since that call has to be safe to make from an HTTP request, which
    cannot block on a terminal prompt (roadmap D8). `ingest.extract()` itself never waits on a
    human; the loop below is CLI-specific glue around it.

    `provider` and `orchestrator` exist so a test can drive this without an API call or a real
    terminal, the same reason `process_md_file_with_ai`'s `orchestrator` param used to.
    `output_dir` defaults to `processor.OUTPUT_DIR`; pass `None` to skip the JSON write (tests
    do, so they do not write into the tracked `output_training_logs_json/` directory).
    """
    from traininglogs.agent.llm_orchestrator import LLMOrchestrator
    from traininglogs.agent.providers import AnthropicProvider
    from traininglogs.agent.schemas import TrainingLogLLMExtract
    from traininglogs.db.fetch import get_extraction
    from traininglogs.db.insert import insert_llm_calls
    from traininglogs.ingest.capture import capture
    from traininglogs.ingest.confirm import confirm
    from traininglogs.ingest.extract import extract
    from traininglogs.processor.processor import (
        OUTPUT_DIR,
        relative_source_file,
        write_session_json,
    )

    if output_dir is _UNSET:
        output_dir = OUTPUT_DIR

    md_text = md_path.read_text(encoding="utf-8")
    source_file = relative_source_file(md_path)
    print(f">>> Loaded training log: {md_path}\n")

    raw_input_id = capture(conn, md_text, source_kind="markdown", source_file=source_file)

    provider = provider or AnthropicProvider()
    extraction_id = extract(conn, raw_input_id, provider=provider, model=provider.model)

    stored = get_extraction(conn, extraction_id)
    pending_extract = TrainingLogLLMExtract.model_validate(stored["extract"])

    orchestrator = orchestrator or LLMOrchestrator(correction_provider=provider)
    # extract() already drained and persisted provider.calls up to this point. The confirm
    # loop below can make more (each correction is its own LLM call, via the same provider
    # instance when the caller shares one) -- those happen after extract() has already
    # returned, so nothing else will ever persist them unless this does.
    calls_recorded_so_far = len(getattr(provider, "calls", []))
    final_extract = orchestrator.confirm_loop(pending_extract)
    insert_llm_calls(conn, raw_input_id, getattr(provider, "calls", [])[calls_recorded_so_far:])

    session = confirm(
        conn,
        extraction_id,
        final_extract,
        md_path=md_path,
        corrections=orchestrator.corrections,
        source_file=source_file,
    )

    print(f">>> Inserted into DB: {session.session_id}\n")
    write_session_json(session, output_dir)
    return session


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="traininglogs log",
        description=(
            "Parse a training log, insert into DB, and commit. "
            "To preview parsing without any DB or git side effects, use 'traininglogs validate' instead."
        ),
    )
    parser.add_argument("target", nargs="?", help="Path to a .md file or directory of .md files")
    parser.add_argument("--program", help="Program name (with --phase and --week)")
    parser.add_argument("--phase", type=int, help="Phase number (used with --program)")
    parser.add_argument("--week", type=int, help="Week number (used with --program)")
    parser.add_argument("--no-commit", action="store_true", help="Insert to DB but skip the git commit")
    parser.add_argument("--pr", action="store_true", help="Create a pull request after committing")
    parser.add_argument("--message", default="", help="Custom commit message")
    parser.add_argument(
        "--parser",
        choices=["ai", "rules"],
        default="ai",
        help="Parser backend: 'ai' (default, LLM-based) or 'rules' (deterministic rule-based).",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Write to TEST_DATABASE_URL only; skip the local mirror. For E2E validation.",
    )

    args = parser.parse_args(argv)

    md_files = _resolve_targets(args.target, args.program, args.phase, args.week)

    print("=" * 60)
    print("TRAINING LOG WORKFLOW")
    print("=" * 60)

    if not _ensure_feature_branch():
        return 1

    print(f"\n[1] Found {len(md_files)} file(s) to process")
    for f in md_files:
        print(f"  {f}")

    from dotenv import load_dotenv
    load_dotenv()

    if args.test:
        database_url = os.environ.get("TEST_DATABASE_URL")
        if not database_url:
            print("\n✗ TEST_DATABASE_URL is not set in .env")
            return 1
    else:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            print("\n✗ DATABASE_URL is not set. Add your Supabase connection string to .env")
            return 1

    print("\n[2] Running parser...")
    import psycopg2
    from traininglogs.db.db import get_connection
    from traininglogs.db.insert import insert_session
    from traininglogs.processor.processor import process_md_file

    conn = get_connection(database_url)

    local_conn = None
    local_url = os.environ.get("LOCAL_DATABASE_URL")
    if local_url and not args.test:
        try:
            local_conn = psycopg2.connect(local_url)
            print("[local db] connected")
        except psycopg2.OperationalError:
            print("[local db] not reachable, skipping")

    try:
        for md_path in md_files:
            if args.parser == "ai":
                session = _process_ai_file(md_path, conn)
            else:
                session = process_md_file(md_path, conn)
            if local_conn:
                try:
                    inserted = insert_session(local_conn, session)
                    if inserted:
                        print(f"[local db] inserted {session.session_id}")
                    else:
                        print(f"[local db] {session.session_id} already exists, skipping")
                except Exception as e:
                    print(f"[local db] insert failed: {e}")
    except SystemExit as e:
        print(str(e))
        return 1
    finally:
        conn.close()
        if local_conn:
            local_conn.close()

    print("✓ Parser completed")

    if args.no_commit:
        print("\n[3] Skipping git commit (--no-commit)")
        _rebuild_dashboard()
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

    _rebuild_dashboard()

    print("\n" + "=" * 60)
    print("✓ WORKFLOW COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
