"""Tests for DeepTrainingParser error handling and parse correctness."""
import pytest
from traininglogs.parser.parse import DeepTrainingParser


# ---------------------------------------------------------------------------
# Minimal session dict used as base for build_training_session tests
# ---------------------------------------------------------------------------
def _base_session(**overrides) -> dict:
    base = {
        "metadata": {
            "date": "2099-01-01",
            "phase": "1",
            "week": "1",
            "duration": "60 min",
            "focus": "Push",
        },
        "exercises": [],
    }
    if overrides:
        base["metadata"].update(overrides)
    return base


# ---------------------------------------------------------------------------
# build_training_session — missing required metadata fields
# ---------------------------------------------------------------------------
class TestBuildTrainingSessionOptionalFields:
    def test_week_without_phase_raises(self):
        # week alone in metadata is malformed — phase is required alongside it
        s = _base_session()
        del s["metadata"]["phase"]
        with pytest.raises(ValueError, match="phase"):
            DeepTrainingParser(s).build_training_session()

    def test_phase_without_week_raises(self):
        # phase alone in metadata is malformed — week is required alongside it
        s = _base_session()
        del s["metadata"]["week"]
        with pytest.raises(ValueError, match="week"):
            DeepTrainingParser(s).build_training_session()

    def test_missing_duration_returns_none(self):
        s = _base_session()
        del s["metadata"]["duration"]
        result = DeepTrainingParser(s).build_training_session()
        assert result["session_duration_minutes"] is None

    def test_unparseable_duration_raises(self):
        s = _base_session(duration="tomorrow")
        with pytest.raises(ValueError, match="duration"):
            DeepTrainingParser(s).build_training_session()

    def test_missing_program_returns_none(self):
        s = _base_session()
        result = DeepTrainingParser(s).build_training_session()
        assert result["program"] is None

    def test_standalone_session_builds_successfully(self):
        s = {
            "metadata": {"date": "2099-08-01", "duration": "45 min"},
            "exercises": [],
        }
        result = DeepTrainingParser(s).build_training_session()
        assert result["phase"] is None
        assert result["week"] is None
        assert result["program"] is None
        assert result["session_duration_minutes"] == 45

    def test_phase_alone_raises(self):
        # phase without week → malformed program session
        s = {
            "metadata": {"date": "2099-08-01", "phase": "3"},
            "exercises": [],
        }
        with pytest.raises(ValueError, match="week"):
            DeepTrainingParser(s).build_training_session()

    def test_week_alone_raises(self):
        # week without phase → malformed program session
        s = {
            "metadata": {"date": "2099-08-01", "week": "1"},
            "exercises": [],
        }
        with pytest.raises(ValueError, match="phase"):
            DeepTrainingParser(s).build_training_session()

    def test_program_session_missing_phase_raises(self):
        s = {
            "metadata": {"date": "2099-08-01", "program": "Test Program", "week": "1"},
            "exercises": [],
        }
        with pytest.raises(ValueError, match="phase"):
            DeepTrainingParser(s).build_training_session()

    def test_program_session_missing_week_raises(self):
        s = {
            "metadata": {"date": "2099-08-01", "program": "Test Program", "phase": "1"},
            "exercises": [],
        }
        with pytest.raises(ValueError, match="week"):
            DeepTrainingParser(s).build_training_session()

    def test_program_session_with_phase_and_week_builds(self):
        s = {
            "metadata": {
                "date": "2099-08-01",
                "program": "Test Program",
                "phase": "2",
                "week": "4",
                "duration": "60 min",
            },
            "exercises": [],
        }
        result = DeepTrainingParser(s).build_training_session()
        assert result["program"] == "Test Program"
        assert result["phase"] == 2
        assert result["week"] == 4


# ---------------------------------------------------------------------------
# _parse_goal — bad goal string raises, absent goal returns None
# ---------------------------------------------------------------------------
class TestParseGoal:
    def _parser(self) -> DeepTrainingParser:
        return DeepTrainingParser({})

    def test_none_goal_returns_none(self):
        assert self._parser()._parse_goal(None, None) is None

    def test_empty_goal_returns_none(self):
        assert self._parser()._parse_goal("", None) is None

    def test_valid_goal(self):
        g = self._parser()._parse_goal("80 kg x 3 sets x 8-10 reps", "3 min")
        assert isinstance(g, dict)
        assert g["weight_kg"] == 80.0
        assert g["sets"] == 3
        assert g["rep_range"] == {"min": 8, "max": 10}
        assert g["rest"] == {"minutes": 3}

    def test_unparseable_goal_raises(self):
        with pytest.raises(ValueError, match="Cannot parse goal"):
            self._parser()._parse_goal("lots of sets", None)


# ---------------------------------------------------------------------------
# _parse_warmup_set_line — bad line raises, good line parses
# ---------------------------------------------------------------------------
class TestParseWarmupSetLine:
    def _parser(self) -> DeepTrainingParser:
        return DeepTrainingParser({})

    def test_valid_warmup_set(self):
        ws = self._parser()._parse_warmup_set_line("1. 40 x 10 - feeling good")
        assert isinstance(ws, dict)
        assert ws["number"] == 1
        assert ws["weight_kg"] == 40.0
        assert ws["rep_count"] == 10

    def test_invalid_line_raises(self):
        with pytest.raises(ValueError, match="Cannot parse warmup set"):
            self._parser()._parse_warmup_set_line("no number here")

    def test_feel_set_parses(self):
        ws = self._parser()._parse_warmup_set_line("2. 60 x feel")
        assert isinstance(ws, dict)
        assert ws["rep_count"] is None


# ---------------------------------------------------------------------------
# _parse_working_set_line — bad line raises, valid lines return correct type
# ---------------------------------------------------------------------------
class TestParseWorkingSetLine:
    def _parser(self) -> DeepTrainingParser:
        return DeepTrainingParser({})

    def test_invalid_line_raises(self):
        with pytest.raises(ValueError, match="Cannot parse working set"):
            self._parser()._parse_working_set_line("not a set line")

    def test_standard_set_returns_dict(self):
        ws = self._parser()._parse_working_set_line("1. 80 x 9 RPE 8 good")
        assert isinstance(ws, dict)
        assert ws["number"] == 1
        assert ws["weight_kg"] == 80.0
        assert ws["rep_count"] == {"full": 9, "partial": 0}
        assert ws["rpe"] == 8.0

    def test_partial_rep_set(self):
        ws = self._parser()._parse_working_set_line("2. 80 x 7 + 2 RPE 9.5 bad")
        assert isinstance(ws, dict)
        assert ws["rep_count"] == {"full": 7, "partial": 2}

    def test_unilateral_set_returns_dict(self):
        result = self._parser()._parse_working_set_line(
            "1. 30 x left: 8 + 1, right: 9 + 1 RPE 8.5 good"
        )
        assert isinstance(result, dict)
        assert result["number"] == 1
        assert result["weight_kg"] == 30.0
        uni = result["unilateral_rep_count"]
        assert uni["left"]["full"] == 8
        assert uni["left"]["partial"] == 1
        assert uni["right"]["full"] == 9
