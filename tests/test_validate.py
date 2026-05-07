from pathlib import Path

import pytest

from traininglogs.cli.validate import main

FIXTURES_VALID = Path(__file__).parent / "fixtures" / "valid"
FIXTURES_INVALID = Path(__file__).parent / "fixtures" / "invalid"


def test_validate_strength_session_exits_zero():
    assert main([str(FIXTURES_VALID / "strength_session.md")]) == 0


def test_validate_activity_session_exits_zero():
    assert main([str(FIXTURES_VALID / "activity_session.md")]) == 0


def test_validate_unilateral_session_exits_zero():
    assert main([str(FIXTURES_VALID / "unilateral_session.md")]) == 0


def test_validate_standalone_session_exits_zero():
    assert main([str(FIXTURES_VALID / "standalone_session.md")]) == 0


def test_validate_missing_file_exits_nonzero():
    assert main(["nonexistent_file.md"]) == 1


def test_validate_malformed_set_line_exits_nonzero():
    assert main([str(FIXTURES_INVALID / "malformed_set_line.md")]) == 1


def test_validate_malformed_goal_exits_nonzero():
    assert main([str(FIXTURES_INVALID / "malformed_goal.md")]) == 1
