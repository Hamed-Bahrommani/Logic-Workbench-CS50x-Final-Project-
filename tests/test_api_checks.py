import json

import pytest

from logic import api
from logic.errors import (
    EMPTY_INPUT, LIMIT_EXCEEDED, UNEXPECTED_END, UNEXPECTED_TOKEN, FormulaError,
)


def chain(prefix, count):
    return " ∧ ".join(f"{prefix}{i}" for i in range(count))


# --- payloads ---

def test_equivalent_payload():
    assert api.equivalent("P -> Q", "~P | Q") == {
        "ok": True,
        "left": {"canonical": "P → Q", "display": "P → Q"},
        "right": {"canonical": "¬P ∨ Q", "display": "¬P ∨ Q"},
        "variables": ["P", "Q"],
        "equivalent": True,
        "distinguishing": None,
    }


def test_a_negative_answer_is_still_ok_true():
    result = api.equivalent("P -> Q", "Q -> P")
    assert result["ok"] is True
    assert result["equivalent"] is False
    assert result["distinguishing"] == {
        "assignment": {"P": True, "Q": False}, "left_value": False, "right_value": True,
    }


def test_valid_payload_for_an_invalid_argument():
    assert api.valid(["P -> Q", "Q"], "P") == {
        "ok": True,
        "premises": [
            {"canonical": "P → Q", "display": "P → Q"},
            {"canonical": "Q", "display": "Q"},
        ],
        "conclusion": {"canonical": "P", "display": "P"},
        "variables": ["P", "Q"],
        "valid": False,
        "vacuous": False,
        "countermodel": {
            "assignment": {"P": False, "Q": True},
            "premise_values": [True, True],
            "conclusion_value": False,
        },
    }


def test_valid_payload_for_a_vacuously_valid_argument():
    result = api.valid(["P", "~P"], "Q")
    assert result["ok"] is True
    assert result["valid"] is True
    assert result["vacuous"] is True
    assert result["countermodel"] is None


def test_valid_with_no_premises():
    result = api.valid([], "P | ~P")
    assert result["ok"] is True
    assert result["premises"] == []
    assert result["valid"] is True
    assert result["vacuous"] is False


# --- errors name the input they are in ---

@pytest.mark.parametrize("left, right, field, code, position", [
    ("P ∧", "Q", "left", UNEXPECTED_END, 3),
    ("P", "∧ Q", "right", UNEXPECTED_TOKEN, 0),
])
def test_equivalent_errors_name_the_field(left, right, field, code, position):
    result = api.equivalent(left, right)
    assert result["ok"] is False
    assert result["error"]["field"] == field
    assert result["error"]["code"] == code
    assert result["error"]["position"] == position


@pytest.mark.parametrize("premises, conclusion, field, code, position", [
    (["P", "Q ∨"], "R", "premise-2", UNEXPECTED_END, 3),
    (["P"], "", "conclusion", EMPTY_INPUT, 0),
    (["∧", "∨"], "P", "premise-1", UNEXPECTED_TOKEN, 0),     # the first bad input is reported
])
def test_valid_errors_name_the_field(premises, conclusion, field, code, position):
    result = api.valid(premises, conclusion)
    assert result["ok"] is False
    assert result["error"]["field"] == field
    assert result["error"]["code"] == code
    assert result["error"]["position"] == position


@pytest.mark.parametrize("call, limit, actual", [
    (lambda: api.equivalent(chain("a", 9), chain("b", 8)), 16, 17),
    (lambda: api.valid(["P"] * 21, "P"), 20, 21),
], ids=["variables", "premises"])
def test_limit_errors_have_no_field(call, limit, actual):
    result = call()
    assert result["ok"] is False
    assert result["error"]["code"] == LIMIT_EXCEEDED
    assert result["error"]["limit"] == limit
    assert result["error"]["actual"] == actual
    assert "field" not in result["error"]


def test_single_formula_errors_have_no_field():
    assert "field" not in api.truth_table("P ∧")["error"]
    assert "field" not in api.parse_formula("P ∧")["error"]


def test_formula_error_to_dict_includes_field_only_when_set():
    error = FormulaError("X", "message", 1)
    assert error.to_dict() == {"code": "X", "message": "message", "position": 1}
    error.field = "left"
    assert error.to_dict() == {"code": "X", "message": "message", "position": 1, "field": "left"}


# --- robustness ---

@pytest.mark.parametrize("call", [
    lambda: api.equivalent("P -> Q", "~P | Q"),
    lambda: api.equivalent("P", "Q"),
    lambda: api.equivalent("P ∧", "Q"),
    lambda: api.valid(["P -> Q", "Q"], "P"),
    lambda: api.valid(["P"] * 21, "P"),
], ids=["equivalent", "not-equivalent", "equivalent-error", "invalid-argument", "premise-limit"])
def test_results_are_json_serialisable(call):
    result = call()
    assert json.loads(json.dumps(result)) == result


def test_checks_never_raise_on_hostile_input():
    junk = ["", "   ", "@", "(" * 5000, "¬" * 5000 + "P", "\x00", "∧∧∧"]
    for text in junk:
        for result in (
            api.equivalent(text, "P"),
            api.equivalent("P", text),
            api.valid([text], "P"),
            api.valid(["P"], text),
        ):
            assert result["ok"] in (True, False)