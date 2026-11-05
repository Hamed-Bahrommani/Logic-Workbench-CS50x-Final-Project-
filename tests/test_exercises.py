import json

import pytest

from exercises import LEVELS, load_exercises
from logic import api
from logic.checks import MAX_PREMISES
from logic.proof import MAX_PROOF_LINES

EXERCISES = load_exercises()


# --- the shipped exercise file ---

def test_there_are_enough_exercises_at_every_level():
    for level in LEVELS:
        assert sum(1 for e in EXERCISES if e["level"] == level) >= 3


def test_ids_are_unique():
    ids = [e["id"] for e in EXERCISES]
    assert len(ids) == len(set(ids))


def test_exercises_are_ordered_by_level():
    levels = [e["level"] for e in EXERCISES]
    assert levels == sorted(levels)


def test_loader_adds_the_joined_texts():
    exercise = next(e for e in EXERCISES if e["id"] == "modus-ponens")
    assert exercise["premises_text"] == "P → Q\nP"
    assert exercise["solution_text"] == "P → Q ; premise\nP ; premise\nQ ; ImpE 1,2"


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e["id"])
def test_every_exercise_is_a_valid_argument(exercise):
    result = api.valid(exercise["premises"], exercise["conclusion"])
    assert result["ok"] is True, result
    assert result["valid"] is True
    # Only the explosion exercise is meant to have contradictory premises.
    assert result["vacuous"] is (exercise["id"] == "from-a-contradiction")


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e["id"])
def test_every_stored_solution_is_a_complete_proof(exercise):
    result = api.check_proof(exercise["premises"], exercise["conclusion"], exercise["solution_text"])
    assert result["ok"] is True, result
    bad = [line for line in result["lines"] if not line["ok"]]
    assert not bad, bad
    assert result["complete"] is True


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e["id"])
def test_exercise_sizes_stay_within_the_limits(exercise):
    assert len(exercise["premises"]) <= MAX_PREMISES
    assert len(exercise["solution"]) <= MAX_PROOF_LINES


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e["id"])
def test_levels_match_the_rules_the_solution_uses(exercise):
    uses_boxes = any(line.lstrip().startswith("|") for line in exercise["solution"])
    assert uses_boxes == (exercise["level"] >= 2)


def test_the_file_keeps_its_unicode_symbols():
    with open("exercises.json", encoding="utf-8") as handle:
        text = handle.read()
    assert "⊥" in text and "→" in text and "∨" in text
    assert "\\u" not in text                  # symbols are stored as themselves, not as escapes


# --- the loader refuses malformed files ---

def good(**changes):
    exercise = {
        "id": "an-id", "title": "A title", "level": 1, "premises": ["P"],
        "conclusion": "P", "hint": "A hint.", "solution": ["P ; premise"],
    }
    exercise.update(changes)
    return exercise


def write(tmp_path, data):
    path = tmp_path / "exercises.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_a_well_formed_file_loads(tmp_path):
    [exercise] = load_exercises(write(tmp_path, [good()]))
    assert exercise["id"] == "an-id"


@pytest.mark.parametrize("data, message", [
    pytest.param({"not": "a list"}, "must be a list", id="not-a-list"),
    pytest.param(["text"], "must be an object", id="not-an-object"),
    pytest.param([{"id": "x"}], "missing", id="missing-fields"),
    pytest.param([dict(good(), extra=1)], "unknown keys", id="unknown-key"),
    pytest.param([good(id="Bad Id")], "bad id", id="bad-id"),
    pytest.param([good(id="trailing-")], "bad id", id="bad-id-trailing-dash"),
    pytest.param([good(), good()], "duplicate id", id="duplicate-id"),
    pytest.param([good(level=9)], "level must be one of", id="unknown-level"),
    pytest.param([good(level=True)], "level must be one of", id="boolean-level"),
    pytest.param([good(title="  ")], "title must be a non-empty string", id="blank-title"),
    pytest.param([good(hint=3)], "hint must be a non-empty string", id="hint-not-text"),
    pytest.param([good(conclusion="")], "conclusion must be a non-empty string", id="blank-conclusion"),
    pytest.param([good(premises="P")], "premises must be a list", id="premises-not-a-list"),
    pytest.param([good(premises=["P", ""])], "premises must be a list", id="blank-premise"),
    pytest.param([good(solution=[])], "solution must be a non-empty list", id="empty-solution"),
    pytest.param([good(solution=["P ; premise", 5])], "solution must be a non-empty list", id="solution-not-text"),
])
def test_loader_rejects_bad_data(tmp_path, data, message):
    with pytest.raises(ValueError, match=message):
        load_exercises(write(tmp_path, data))


def test_loader_rejects_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="cannot read exercises"):
        load_exercises(tmp_path / "nope.json")


def test_loader_rejects_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("[{", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot read exercises"):
        load_exercises(path)
