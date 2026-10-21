"""Gather the changelog fragments in changelog.d/ into CHANGELOG.md at release time.

Each pull request that changes behaviour adds one file, `changelog.d/<issue>.<section>.md`, where
<issue> is the issue it fixes (or a short name when there is none) and <section> is one of
added, changed, fixed, removed. The file holds the entry as it should read in the changelog. Two
pull requests never edit the same file, so they never conflict.

    .venv/bin/python scripts/changelog.py                    # show what the next release would say
    .venv/bin/python scripts/changelog.py --release 5.1.0    # write it into CHANGELOG.md, delete the fragments
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTIONS = {"added": "Added", "changed": "Changed", "fixed": "Fixed", "removed": "Removed"}
NAME = re.compile(r"^(?P<id>[a-z0-9][a-z0-9-]*)\.(?P<section>[a-z]+)\.md$")
UNRELEASED_LINK = re.compile(r"^\[Unreleased\]: (?P<base>\S+)/compare/v(?P<previous>[\w.]+)\.\.\.HEAD$", re.M)


def check_names(folder: Path) -> list[str]:
    """Why each fragment name is wrong, one line per bad file; empty when all are fine."""
    problems = []
    for path in sorted(folder.glob("*")):
        if path.name == "README.md":
            continue
        match = NAME.match(path.name)
        if not match:
            problems.append(f"{path.name}: name it <issue>.<section>.md, e.g. 63.fixed.md")
        elif match["section"] not in SECTIONS:
            problems.append(f"{path.name}: section must be one of {', '.join(SECTIONS)}")
        elif not path.read_text().strip():
            problems.append(f"{path.name}: empty")
    return problems


def _issue_order(path: Path) -> tuple[int, str]:
    """Numbered fragments in number order, named ones after them."""
    first = path.name.split(".")[0]
    return (int(first), "") if first.isdigit() else (sys.maxsize, first)


def _entry(text: str) -> str:
    """A fragment as a list item: '- ' before the first line, two spaces before the rest."""
    text = text.strip()
    if text.startswith("- "):
        return text
    lines = text.splitlines()
    return "\n".join([f"- {lines[0]}", *(f"  {line}" if line else line for line in lines[1:])])


def render(folder: Path) -> str:
    """The fragments as changelog sections, in Keep a Changelog order; empty when there are none."""
    blocks = []
    for key, heading in SECTIONS.items():
        paths = sorted(folder.glob(f"*.{key}.md"), key=_issue_order)
        if paths:
            entries = "\n".join(_entry(p.read_text()) for p in paths)
            blocks.append(f"### {heading}\n\n{entries}")
    return "\n\n".join(blocks)


def release(changelog: Path, folder: Path, version: str, date: str) -> None:
    """Write the fragments under `## [version] - date`, update the compare links, delete them."""
    problems = check_names(folder)
    if problems:
        raise SystemExit("\n".join(problems))
    body = render(folder)
    if not body:
        raise SystemExit("No fragments in changelog.d/: nothing to release.")
    text = changelog.read_text()
    link = UNRELEASED_LINK.search(text)
    if not link:
        raise SystemExit("CHANGELOG.md has no '[Unreleased]: .../compare/v<version>...HEAD' link.")
    marker = "\n## ["
    first_release = text.index(marker, text.index("## [Unreleased]") + 1)
    text = f"{text[:first_release]}\n## [{version}] - {date}\n\n{body}\n{text[first_release:]}"
    base, previous = link["base"], link["previous"]
    text = text.replace(
        link[0],
        f"[Unreleased]: {base}/compare/v{version}...HEAD\n[{version}]: {base}/compare/v{previous}...v{version}",
    )
    changelog.write_text(text)
    for path in folder.glob("*.md"):
        if path.name != "README.md":
            path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--release", metavar="VERSION", help="write the fragments into CHANGELOG.md as this version")
    parser.add_argument("--date", default=datetime.date.today().isoformat(), help="release date, YYYY-MM-DD")
    args = parser.parse_args()
    folder = ROOT / "changelog.d"
    if args.release:
        release(ROOT / "CHANGELOG.md", folder, args.release, args.date)
        print(f"CHANGELOG.md: wrote [{args.release}] - {args.date}; fragments deleted.")
    else:
        problems = check_names(folder)
        print("\n".join(problems) if problems else render(folder) or "No fragments in changelog.d/.")


if __name__ == "__main__":
    main()
