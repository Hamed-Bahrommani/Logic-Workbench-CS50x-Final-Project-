# AI assistance (CS50x final project rule): drafted with Claude (Anthropic) in a
import pytest

from logic import api
from logic.proof import split_proof_text

POOL = ["P", "Q", "¬P", "¬Q", "¬¬P", "P ∧ Q", "P ∨ Q", "P → Q", "P ↔ Q", "⊥"]


def run(premises, conclusion, text):
    outcome = api.check_proof(premises, conclusion, text)
    assert outcome["ok"] is True, outcome
    return outcome


def codes(outcome):
    return [(line["error"] or {}).get("code") for line in outcome["lines"]]


# --- reading the bars ---

@pytest.mark.parametrize("line, formula, depth", [
    pytest.param("P ; premise", "P", 0, id="no-bar"),
    pytest.param("| P ; assume", "P", 1, id="one-bar"),
    pytest.param("|P ; assume", "P", 1, id="no-space"),
    pytest.param("| | P ; assume", "P", 2, id="two-bars"),
    pytest.param("||P ; assume", "P", 2, id="two-bars-no-space"),
    pytest.param("3. | P ; assume", "P", 1, id="line-number-then-bar"),
])
def test_bars_set_the_depth(line, formula, depth):
    [entry] = split_proof_text(line)
    assert (entry.formula_text, entry.depth) == (formula, depth)


# --- complete proofs with boxes ---

def test_p_implies_p():
    outcome = run([], "P → P", "| P ; assume\nP → P ; ImpI 1-1")
    assert outcome["complete"]
    assert [line["depth"] for line in outcome["lines"]] == [1, 0]
    assert outcome["lines"][1]["refs"] == ["1-1"]


def test_contraposition_with_nested_boxes():
    text = "\n".join([
        "P → Q ; premise",
        "| ¬Q ; assume",
        "| | P ; assume",
        "| | Q ; ImpE 1,3",
        "| | ⊥ ; NotE 4,2",
        "| ¬P ; NotI 3-5",
        "¬Q → ¬P ; ImpI 2-6",
    ])
    outcome = run(["P → Q"], "¬Q → ¬P", text)
    assert outcome["complete"], outcome["lines"]
    assert [line["depth"] for line in outcome["lines"]] == [0, 1, 2, 2, 2, 1, 0]


def test_nested_implication_introduction():
    text = "\n".join([
        "| P ; assume",
        "| | Q ; assume",
        "| | P ; R 1",
        "| Q → P ; ImpI 2-3",
        "P → (Q → P) ; ImpI 1-4",
    ])
    assert run([], "P → (Q → P)", text)["complete"]


def test_or_elimination_with_sibling_boxes():
    text = "\n".join([
        "P ∨ Q ; premise",
        "| P ; assume",
        "| Q ∨ P ; OrI 2",
        "| Q ; assume",
        "| Q ∨ P ; OrI 4",
        "Q ∨ P ; OrE 1,2-3,4-5",
    ])
    assert run(["P ∨ Q"], "Q ∨ P", text)["complete"]


def test_iff_introduction():
    text = "\n".join([
        "| P ∧ Q ; assume",
        "| P ; AndE 1",
        "| Q ; AndE 1",
        "| Q ∧ P ; AndI 3,2",
        "| Q ∧ P ; assume",
        "| Q ; AndE 5",
        "| P ; AndE 5",
        "| P ∧ Q ; AndI 7,6",
        "(P ∧ Q) ↔ (Q ∧ P) ; IffI 1-4,5-8",
    ])
    assert run([], "(P ∧ Q) ↔ (Q ∧ P)", text)["complete"]


@pytest.mark.parametrize("alias", ["→I", "->I", "impi", "IMPI"])
def test_subproof_rule_spellings(alias):
    outcome = run([], "P → P", f"| P ; assume\nP → P ; {alias} 1-1")
    assert outcome["lines"][1]["rule"] == "ImpI"
    assert outcome["complete"]


@pytest.mark.parametrize("alias", ["Assume", "assume", "Hyp"])
def test_assume_spellings(alias):
    outcome = run([], "P → P", f"| P ; {alias}\nP → P ; ImpI 1-1")
    assert outcome["lines"][0]["rule"] == "Assume"


def test_premises_may_be_restated_inside_a_box():
    outcome = run(["P"], "P", "| Q ; assume\n| P ; premise")
    assert all(line["ok"] for line in outcome["lines"])


# --- when a proof is not finished ---

def test_ending_inside_a_box_is_not_complete():
    outcome = run([], "P", "| P ; assume")
    assert outcome["valid"] is True
    assert outcome["in_subproof"] is True
    assert outcome["complete"] is False


def test_conclusion_inside_a_box_does_not_count():
    outcome = run(["P"], "P", "| Q ; assume\n| P ; premise")
    assert outcome["valid"] is True
    assert outcome["complete"] is False


# --- indentation errors ---

@pytest.mark.parametrize("premises, text, line_index", [
    pytest.param([], "P ; Assume", 0, id="assume-without-a-bar"),
    pytest.param([], "| | P ; assume", 0, id="box-opened-too-deep"),
    pytest.param(["P"], "| P ; premise", 0, id="indent-without-assume"),
    pytest.param(["Q"], "| P ; assume\n| | Q ; premise", 1, id="indent-jump-inside-a-box"),
])
def test_indentation_errors(premises, text, line_index):
    outcome = run(premises, "P", text)
    assert outcome["lines"][line_index]["error"]["code"] == "BAD_INDENT"


# --- scope ---

def test_a_closed_box_cannot_be_cited_line_by_line():
    outcome = run([], "P", "| P ; assume\nP → P ; ImpI 1-1\nP ; R 1")
    assert codes(outcome) == [None, None, "OUT_OF_SCOPE"]


def test_an_open_box_cannot_be_cited_as_a_range():
    outcome = run([], "P", "| P ; assume\n| P → P ; ImpI 1-1")
    assert outcome["lines"][1]["error"]["code"] == "OUT_OF_SCOPE"
    assert "still open" in outcome["lines"][1]["error"]["message"]


def test_a_box_inside_a_closed_box_cannot_be_cited():
    text = "\n".join([
        "| P ; assume",
        "| | Q ; assume",
        "| Q → Q ; ImpI 2-2",
        "P → (Q → Q) ; ImpI 1-3",
        "Q → Q ; ImpI 2-2",
    ])
    outcome = run([], "Q → Q", text)
    assert codes(outcome) == [None, None, None, None, "OUT_OF_SCOPE"]


def test_a_range_must_start_at_an_assume():
    outcome = run(["P"], "P", "P ; premise\n| P ; assume\nP → P ; ImpI 1-2")
    assert outcome["lines"][2]["error"]["code"] == "BAD_RANGE"


def test_a_range_must_end_where_the_box_ends():
    outcome = run(["P"], "P", "P ; premise\n| P ; assume\n| P ; R 1\nP → P ; ImpI 2-2")
    error = outcome["lines"][3]["error"]
    assert error["code"] == "BAD_RANGE"
    assert "ends at line 3" in error["message"]


@pytest.mark.parametrize("text, line_index, code", [
    pytest.param("P ; premise\nP → P ; ImpI 1", 1, "WRONG_REFERENCE_COUNT", id="impi-with-a-line"),
    pytest.param("P ∧ Q ; premise\nP ; AndE 1-1", 1, "BAD_REFERENCE", id="line-rule-with-a-range"),
    pytest.param("| P ; assume 1", 0, "WRONG_REFERENCE_COUNT", id="assume-with-a-reference"),
    pytest.param("| P ; assume\n| P ; R 1\nP → P ; ImpI 1-9", 2, "BAD_REFERENCE", id="range-end-not-earlier"),
])
def test_citation_shape_errors(text, line_index, code):
    outcome = run(["P"] if text.startswith("P ;") or text.startswith("P ∧") else [], "P", text)
    assert outcome["lines"][line_index]["error"]["code"] == code


# --- the subproof rules refuse what they should ---

def test_impi_wrong_result():
    outcome = run([], "P", "| P ; assume\nP → Q ; ImpI 1-1")
    assert outcome["lines"][1]["error"]["code"] == "RESULT_MISMATCH"


def test_noti_needs_a_box_ending_in_falsum():
    outcome = run([], "P", "| P ; assume\n¬P ; NotI 1-1")
    assert outcome["lines"][1]["error"]["code"] == "RULE_PATTERN"


def test_noti_wrong_result():
    text = "¬P ; premise\n| P ; assume\n| ⊥ ; NotE 2,1\n¬Q ; NotI 2-3"
    outcome = run(["¬P"], "¬Q", text)
    assert outcome["lines"][3]["error"]["code"] == "RESULT_MISMATCH"


def test_iffi_needs_matching_boxes():
    text = "| P ; assume\n| P ; R 1\n| Q ; assume\n| Q ; R 3\nP ↔ Q ; IffI 1-2,3-4"
    outcome = run([], "P ↔ Q", text)
    assert outcome["lines"][4]["error"]["code"] == "RULE_PATTERN"


def test_ore_needs_a_disjunction():
    text = "\n".join([
        "P ; premise", "Q ; premise",
        "| P ; assume", "| P ; R 1", "| Q ; assume", "| P ; R 1",
        "P ; OrE 1,3-4,5-6",
    ])
    outcome = run(["P", "Q"], "P", text)
    assert outcome["lines"][6]["error"]["code"] == "RULE_PATTERN"
    assert "is not one" in outcome["lines"][6]["error"]["message"]


def test_ore_boxes_must_assume_the_two_sides():
    text = "\n".join([
        "P ∨ Q ; premise", "P ; premise",
        "| P ; assume", "| P ; R 2", "| R ; assume", "| P ; R 2",
        "P ; OrE 1,3-4,5-6",
    ])
    outcome = run(["P ∨ Q", "P"], "P", text)
    error = outcome["lines"][6]["error"]
    assert error["code"] == "RULE_PATTERN"
    assert "two sides" in error["message"]


def test_ore_boxes_must_end_in_the_same_formula():
    text = "\n".join([
        "P ∨ Q ; premise", "P ; premise", "Q ; premise",
        "| P ; assume", "| P ; R 2", "| Q ; assume", "| Q ; R 3",
        "P ; OrE 1,4-5,6-7",
    ])
    outcome = run(["P ∨ Q", "P", "Q"], "P", text)
    error = outcome["lines"][7]["error"]
    assert error["code"] == "RULE_PATTERN"
    assert "same formula" in error["message"]


# --- soundness of the box rules ---

@pytest.mark.parametrize("a", POOL)
def test_impi_is_sound(a):
    accepted = 0
    for b in POOL:
        for result in POOL:
            text = f"{b} ; premise\n| {a} ; assume\n| {b} ; R 1\n{result} ; ImpI 2-3"
            outcome = run([b], result, text)
            if outcome["lines"][-1]["ok"]:
                accepted += 1
                assert outcome["complete"]
                assert api.valid([b], result)["valid"], (a, b, result)
    assert accepted >= 0     # soundness is the assertion above; usability is covered by the worked proofs


def test_noti_is_sound_and_usable():
    accepted = 0
    for a in POOL:
        premise = f"¬({a})"
        for result in POOL:
            text = f"{premise} ; premise\n| {a} ; assume\n| ⊥ ; NotE 2,1\n{result} ; NotI 2-3"
            outcome = run([premise], result, text)
            if outcome["lines"][-1]["ok"]:
                accepted += 1
                assert api.valid([premise], result)["valid"], (a, result)
    assert accepted > 0


def test_ore_is_sound_and_usable():
    accepted = 0
    for a in POOL:
        for b in POOL:
            disjunction = f"({a}) ∨ ({b})"
            for c in POOL:
                premises = [disjunction, c]
                text = "\n".join([
                    f"{disjunction} ; premise", f"{c} ; premise",
                    f"| {a} ; assume", f"| {c} ; R 2",
                    f"| {b} ; assume", f"| {c} ; R 2",
                    f"{c} ; OrE 1,3-4,5-6",
                ])
                outcome = run(premises, c, text)
                if outcome["lines"][-1]["ok"]:
                    accepted += 1
                    assert api.valid(premises, c)["valid"]
    assert accepted > 0