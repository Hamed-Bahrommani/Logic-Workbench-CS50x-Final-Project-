import json

import pytest

from logic import api
from logic.errors import (
    EMPTY_INPUT, LIMIT_EXCEEDED, UNEXPECTED_END, UNEXPECTED_TOKEN,
)


# --- parse_formula ---

def test_parse_formula_payload():
    result = api.parse_formula("~P & (Q -> R)")
    assert result["ok"] is True
    assert result["canonical"] == "¬P ∧ (Q → R)"
    assert result["variables"] == ["P", "Q", "R"]
    assert result["ast"] == {
        "type": "and",
        "left": {"type": "not", "child": {"type": "var", "name": "P"}},
        "right": {
            "type": "imp",
            "left": {"type": "var", "name": "Q"},
            "right": {"type": "var", "name": "R"},
        },
    }


def test_parse_formula_ast_for_every_node_type():
    types = set()

    def walk(node):
        types.add(node["type"])
        for key in ("child", "left", "right"):
            if key in node:
                walk(node[key])

    walk(api.parse_formula("¬(P ∧ Q) ∨ (R → S) ↔ ⊥")["ast"])
    assert types == {"not", "and", "or", "imp", "iff", "var", "bot"}


@pytest.mark.parametrize("text, code, position", [
    ("", EMPTY_INPUT, 0),
    ("P ∧", UNEXPECTED_END, 3),
    ("P Q", UNEXPECTED_TOKEN, 2),
])
def test_parse_formula_errors(text, code, position):
    result = api.parse_formula(text)
    assert result["ok"] is False
    assert result["error"]["code"] == code
    assert result["error"]["position"] == position
    assert result["error"]["message"]


# --- truth_table ---

def test_truth_table_payload():
    result = api.truth_table("P -> Q")
    assert result["ok"] is True
    assert result["canonical"] == "P → Q"
    assert result["variables"] == ["P", "Q"]
    assert result["classification"] == "contingency"
    assert result["satisfiable"] is True
    assert [r["value"] for r in result["rows"]] == [True, False, True, True]
    assert result["rows_omitted"] is False


def test_logically_negative_answers_are_still_ok_true():
    result = api.truth_table("P ∧ ¬P")
    assert result["ok"] is True
    assert result["classification"] == "contradiction"
    assert result["satisfiable"] is False


def test_truth_table_syntax_error_is_ok_false():
    result = api.truth_table("P ↔ Q ↔ R")
    assert result["ok"] is False
    assert result["error"]["code"] == "NON_ASSOCIATIVE"
    assert result["error"]["position"] == 6
    assert "rows" not in result


def test_truth_table_limit_exceeded_is_ok_false():
    text = " ∧ ".join(f"v{i}" for i in range(17))
    result = api.truth_table(text)
    assert result["ok"] is False
    assert result["error"]["code"] == LIMIT_EXCEEDED
    assert result["error"]["limit"] == 16
    assert result["error"]["actual"] == 17


def test_truth_table_rows_omitted_envelope():
    text = " ∧ ".join(f"v{i}" for i in range(10))
    result = api.truth_table(text)
    assert result["ok"] is True
    assert result["rows_omitted"] is True
    assert "rows" not in result
    assert result["row_count"] == 1024


def test_truth_table_never_raises_on_hostile_input():
    for text in ["", "   ", "@", "(" * 5000, "¬" * 5000 + "P", "P" * 100000, "\x00", "∧∧∧"]:
        result = api.truth_table(text)
        assert result["ok"] in (True, False)


# --- every result must be JSON-serialisable (Flask will jsonify them) ---

@pytest.mark.parametrize("call", [
    lambda: api.parse_formula("P ∧ Q"),
    lambda: api.parse_formula("P ∧"),
    lambda: api.truth_table("P → (Q ∧ ¬R)"),
    lambda: api.truth_table("⊥"),
    lambda: api.truth_table("P ∧"),
    lambda: api.truth_table(" ∧ ".join(f"v{i}" for i in range(10))),
    lambda: api.truth_table(" ∧ ".join(f"v{i}" for i in range(17))),
], ids=["parse-ok", "parse-error", "table-spec-example", "table-bottom",
        "table-syntax-error", "table-rows-omitted", "table-limit-exceeded"])
def test_results_are_json_serialisable(call):
    result = call()
    assert json.loads(json.dumps(result)) == result