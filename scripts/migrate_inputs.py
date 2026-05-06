"""
Migrate existing training logs from input_training_logs_md/ into the new inputs/ structure.

Source layout:  input_training_logs_md/phase N week N/<file>.md
Target layout:  inputs/programs/<program_slug>/phase_N/week_N/<file>.md

The program slug is derived from the "- Program:" metadata line in each file,
falling back to "bodybuilding_transformation_system" (the known default).

Run once after cutting feature/inputs-restructure. Safe to re-run — existing
files are skipped unless --overwrite is passed.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = PROJECT_ROOT / "input_training_logs_md"
INPUTS_ROOT = PROJECT_ROOT / "inputs"

_DEFAULT_PROGRAM = "bodybuilding_transformation_system"
_DIR_PATTERN = re.compile(r"^phase (\d+) week (\d+)$", re.IGNORECASE)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _program_slug(md_path: Path) -> str:
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return _DEFAULT_PROGRAM
    for line in text.splitlines():
        m = re.match(r"^-\s*Program:\s*(.+)", line, re.IGNORECASE)
        if m:
            return _slugify(m.group(1).strip())
    return _DEFAULT_PROGRAM


def migrate(dry_run: bool = False, overwrite: bool = False) -> None:
    if not SOURCE_ROOT.exists():
        print(f"ERROR: source directory not found: {SOURCE_ROOT}", file=sys.stderr)
        sys.exit(1)

    copied = skipped = 0

    for phase_week_dir in sorted(SOURCE_ROOT.iterdir()):
        if not phase_week_dir.is_dir():
            continue
        m = _DIR_PATTERN.match(phase_week_dir.name)
        if not m:
            continue
        phase, week = int(m.group(1)), int(m.group(2))

        for md_path in sorted(phase_week_dir.glob("*.md")):
            slug = _program_slug(md_path)
            dest_dir = INPUTS_ROOT / "programs" / slug / f"phase_{phase}" / f"week_{week}"
            dest = dest_dir / md_path.name

            if dest.exists() and not overwrite:
                print(f"  skip (exists): {dest.relative_to(PROJECT_ROOT)}")
                skipped += 1
                continue

            print(f"  copy: {md_path.relative_to(PROJECT_ROOT)} → {dest.relative_to(PROJECT_ROOT)}")
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(md_path, dest)
            copied += 1

    print(f"\nDone. Copied: {copied}  Skipped: {skipped}{'  [DRY RUN]' if dry_run else ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without doing it")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files in inputs/")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
