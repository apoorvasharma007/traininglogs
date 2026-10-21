"""scripts/changelog.py: fragments in changelog.d/ become a release section in CHANGELOG.md."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("changelog", ROOT / "scripts" / "changelog.py")
changelog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(changelog)

BASE = "https://github.com/o/r"
CHANGELOG = f"""# Changelog

## [Unreleased]

Unreleased changes are in `changelog.d/`.

## [1.0.0] - 2026-01-01

### Added

- The first thing.

[Unreleased]: {BASE}/compare/v1.0.0...HEAD
[1.0.0]: {BASE}/releases/tag/v1.0.0
"""


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    folder = tmp_path / "changelog.d"
    folder.mkdir()
    (folder / "README.md").write_text("How to add a fragment.")
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG)
    return path, folder


def test_release_writes_sections_in_order_and_deletes_the_fragments(repo: tuple[Path, Path]) -> None:
    path, folder = repo
    (folder / "64.fixed.md").write_text("Second fix.\n")
    (folder / "9.fixed.md").write_text("First fix, which is long\nenough to wrap.\n")
    (folder / "cleanup.changed.md").write_text("A change.\n")
    (folder / "70.added.md").write_text("- Already a list item.\n")

    changelog.release(path, folder, "1.1.0", "2026-02-02")

    assert path.read_text() == f"""# Changelog

## [Unreleased]

Unreleased changes are in `changelog.d/`.

## [1.1.0] - 2026-02-02

### Added

- Already a list item.

### Changed

- A change.

### Fixed

- First fix, which is long
  enough to wrap.
- Second fix.

## [1.0.0] - 2026-01-01

### Added

- The first thing.

[Unreleased]: {BASE}/compare/v1.1.0...HEAD
[1.1.0]: {BASE}/compare/v1.0.0...v1.1.0
[1.0.0]: {BASE}/releases/tag/v1.0.0
"""
    assert [p.name for p in folder.iterdir()] == ["README.md"]


def test_release_refuses_a_badly_named_fragment_and_changes_nothing(repo: tuple[Path, Path]) -> None:
    path, folder = repo
    (folder / "63.fix.md").write_text("Wrong section.\n")

    with pytest.raises(SystemExit, match="63.fix.md: section must be one of"):
        changelog.release(path, folder, "1.1.0", "2026-02-02")
    assert path.read_text() == CHANGELOG
    assert (folder / "63.fix.md").exists()


def test_release_with_no_fragments_refuses(repo: tuple[Path, Path]) -> None:
    path, folder = repo
    with pytest.raises(SystemExit, match="nothing to release"):
        changelog.release(path, folder, "1.1.0", "2026-02-02")


def test_check_names_flags_bad_names_and_empty_files(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("x")
    (tmp_path / "12.fixed.md").write_text("  \n")
    (tmp_path / "13.fixed.md").write_text("Fine.")
    assert changelog.check_names(tmp_path) == [
        "12.fixed.md: empty",
        "notes.md: name it <issue>.<section>.md, e.g. 63.fixed.md",
    ]


def test_the_repos_own_fragments_are_named_right() -> None:
    """Runs on every pull request, so a bad fragment fails CI instead of the release."""
    assert changelog.check_names(ROOT / "changelog.d") == []
