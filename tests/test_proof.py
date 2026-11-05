import itertools

import pytest

from logic import api
from logic.errors import LIMIT_EXCEEDED
from logic.proof import MAX_PROOF_LINES, RULES, split_proof_text


def proof(premises, *rest):
    """Proof text: one 'premise' line per premise, then the given lines."""
    return "\n".join([f"{p} ; premise" for p in premises] + list(rest))


def check(premises, conclusion, text):
    outcome = api.check_proof(premises, conclusion, text)
    assert outcome["ok"] is True, outcome
    return outcome


# --- correct proofs ---

def test_modus_ponens():
    outcome = check(["P → Q", "P"], "Q", "P → Q ; premise\nP ; premise\nQ ; ImpE 1,2")
    assert outcome["valid"] and outcome["complete"]
    assert outcome["error_count"] == 0
    assert outcome["lines"][2]["rule"] == "ImpE"
    assert outcome["lines"][2]["refs"] == [1, 2]


def test_conjunction_swap():
    text = "P ∧ Q ; premise\nP ; AndE 1\nQ ; AndE 1\nQ ∧ P ; AndI 3,2"
    outcome = check(["P ∧ Q"], "Q ∧ P", text)
    assert outcome["valid"] and outcome["complete"]


@pytest.mark.parametrize("premise, line", [
    pytest.param("P", "P ∨ Q ; OrI 1", id="left"),
    pytest.param("Q", "P ∨ Q ; OrI 1", id="right"),
])
def test_or_introduction_on_either_side(premise, line):
    outcome = check([premise], "P ∨ Q", proof([premise], line))
    assert outcome["complete"]


@pytest.mark.parametrize("premises, conclusion", [
    pytest.param(["P ↔ Q", "P"], "Q", id="left-to-right"),
    pytest.param(["P ↔ Q", "Q"], "P", id="right-to-left"),
])
def test_biconditional_elimination_both_ways(premises, conclusion):
    outcome = check(premises, conclusion, proof(premises, f"{conclusion} ; IffE 1,2"))
    assert outcome["complete"]


def test_double_negation_elimination():
    assert check(["¬¬P"], "P", proof(["¬¬P"], "P ; DNE 1"))["complete"]


def test_explosion():
    text = proof(["P", "¬P"], "⊥ ; NotE 1,2", "Q ; BotE 3")
    assert check(["P", "¬P"], "Q", text)["complete"]


def test_reiteration():
    assert check(["P"], "P", proof(["P"], "P ; R 1"))["complete"]


def test_hypothetical_syllogism_with_a_witness():
    premises = ["P → Q", "Q → R", "P"]
    text = proof(premises, "Q ; ImpE 1,3", "R ; ImpE 2,4")
    assert check(premises, "R", text)["complete"]


def test_ascii_spellings_and_typed_line_numbers():
    text = "1. P -> Q ; premise\n2. P ; premise\n3) Q ; ->E 1,2"
    assert check(["P -> Q", "P"], "Q", text)["complete"]


def test_blank_lines_are_ignored_and_numbering_follows_the_lines_kept():
    text = "\nP ; premise\n\n   \nP ∨ Q ; OrI 1\n"
    outcome = check(["P"], "P ∨ Q", text)
    assert [line["number"] for line in outcome["lines"]] == [1, 2]
    assert outcome["complete"]


@pytest.mark.parametrize("spelling", ["AndI", "andi", "ANDI", "∧I", "&I"])
def test_rule_spellings(spelling):
    text = proof(["P", "Q"], f"P ∧ Q ; {spelling} 1,2")
    outcome = check(["P", "Q"], "P ∧ Q", text)
    assert outcome["lines"][-1]["rule"] == "AndI"
    assert outcome["lines"][-1]["ok"]


def test_refs_may_be_separated_by_spaces_or_commas():
    for refs in ("1,2", "1, 2", "1 2"):
        text = proof(["P → Q", "P"], f"Q ; ImpE {refs}")
        assert check(["P → Q", "P"], "Q", text)["lines"][-1]["ok"]


def test_lines_are_shown_with_explicit_grouping():
    outcome = check(["P → Q ∧ R"], "P → Q ∧ R", "P → Q ∧ R ; premise")
    assert outcome["lines"][0]["formula"] == "P → (Q ∧ R)"


# --- valid but not finished ---

def test_correct_lines_that_do_not_reach_the_conclusion():
    outcome = check(["P"], "Q", "P ; premise")
    assert outcome["valid"] is True
    assert outcome["complete"] is False


def test_the_conclusion_must_be_the_last_line():
    outcome = check(["P"], "P", "P ; premise\nP ∨ Q ; OrI 1")
    assert outcome["valid"] is True
    assert outcome["complete"] is False


# --- line-level errors ---

def first_error(outcome):
    return next(line for line in outcome["lines"] if not line["ok"])


def test_missing_separator():
    outcome = check(["P → Q"], "P → Q", "P → Q premise")
    assert outcome["valid"] is False and outcome["complete"] is False
    assert outcome["lines"][0]["error"]["code"] == "BAD_LINE_SYNTAX"


def test_formula_syntax_error_keeps_its_position():
    outcome = check(["P"], "P", "P ∧ ; premise")
    error = outcome["lines"][0]["error"]
    assert error["code"] == "UNEXPECTED_END"
    assert error["position"] == 3
    assert error["part"] == "formula"


def test_unknown_rule():
    outcome = check(["P"], "P", "P ; magic 1")
    assert outcome["lines"][0]["error"]["code"] == "UNKNOWN_RULE"
    assert "magic" in outcome["lines"][0]["error"]["message"]


def test_missing_rule():
    outcome = check(["P"], "P", "P ;")
    assert outcome["lines"][0]["error"]["code"] == "UNKNOWN_RULE"


def test_wrong_number_of_references():
    outcome = check(["P"], "P ∧ P", "P ; premise\nP ∧ P ; AndI 1")
    error = outcome["lines"][1]["error"]
    assert error["code"] == "WRONG_REFERENCE_COUNT"
    assert "needs 2 line numbers" in error["message"]


def test_premise_with_a_reference():
    outcome = check(["P"], "P", "P ; premise 1")
    assert outcome["lines"][0]["error"]["code"] == "WRONG_REFERENCE_COUNT"


def test_reference_that_is_not_a_number():
    outcome = check(["P ∧ Q"], "Q", "P ∧ Q ; premise\nQ ; AndE a")
    assert outcome["lines"][1]["error"]["code"] == "BAD_REFERENCE"


@pytest.mark.parametrize("line", [
    pytest.param("P ; R 1", id="itself"),
    pytest.param("P ; R 3", id="later-line"),
    pytest.param("P ; R 0", id="zero"),
])
def test_reference_must_be_an_earlier_line(line):
    outcome = check(["P"], "P", f"P ; premise\n{line}" if line != "P ; R 1" else line)
    assert first_error(outcome)["error"]["code"] == "BAD_REFERENCE"


def test_citing_a_line_with_a_broken_formula():
    outcome = check(["P"], "P", "P @ Q ; premise\nP ; AndE 1")
    assert outcome["lines"][0]["ok"] is False
    assert outcome["lines"][1]["error"]["code"] == "BAD_REFERENCE"
    assert outcome["error_count"] == 2


def test_citing_a_line_whose_rule_failed_is_allowed():
    # Line 1 claims a premise that is not one; line 2 is judged on its own.
    outcome = check(["P"], "Q", "Q ∧ R ; premise\nQ ; AndE 1")
    assert outcome["lines"][0]["error"]["code"] == "NOT_A_PREMISE"
    assert outcome["lines"][1]["ok"] is True


def test_not_a_premise():
    outcome = check(["P"], "Q", "Q ; premise")
    assert outcome["lines"][0]["error"]["code"] == "NOT_A_PREMISE"


def test_every_bad_line_is_reported():
    # Line 1 is not a premise; line 2 has an unknown rule; line 3 correctly
    # repeats line 1's claim, so it is judged on its own and passes.
    outcome = check(["P"], "P", "Q ; premise\nP ; magic 1\nQ ; R 1")
    assert outcome["error_count"] == 2
    assert [line["ok"] for line in outcome["lines"]] == [False, False, True]

# --- rules applied to the wrong formulas, or giving the wrong result ---

@pytest.mark.parametrize("premises, last, code", [
    # the cited lines have the wrong shape
    pytest.param(["P", "Q"], "Q ; ImpE 1,2", "RULE_PATTERN", id="impe-no-implication"),
    pytest.param(["P"], "P ; AndE 1", "RULE_PATTERN", id="ande-not-a-conjunction"),
    pytest.param(["P", "Q"], "P ; IffE 1,2", "RULE_PATTERN", id="iffe-no-biconditional"),
    pytest.param(["P"], "P ; DNE 1", "RULE_PATTERN", id="dne-not-double-negation"),
    pytest.param(["P"], "P ; BotE 1", "RULE_PATTERN", id="bote-not-falsum"),
    pytest.param(["P", "Q"], "⊥ ; NotE 1,2", "RULE_PATTERN", id="note-not-a-pair"),
    pytest.param(["P → Q", "Q"], "P ; ImpE 1,2", "RULE_PATTERN", id="impe-wrong-antecedent"),
    # the shape is right but the result is not what the rule gives
    pytest.param(["P ∧ Q"], "R ; AndE 1", "RESULT_MISMATCH", id="ande-wrong-result"),
    pytest.param(["P → Q", "P"], "P ; ImpE 1,2", "RESULT_MISMATCH", id="impe-wrong-result"),
    pytest.param(["P", "Q"], "P ∧ R ; AndI 1,2", "RESULT_MISMATCH", id="andi-wrong-result"),
    pytest.param(["P"], "Q ∨ R ; OrI 1", "RESULT_MISMATCH", id="ori-wrong-result"),
    pytest.param(["P", "¬P"], "Q ; NotE 1,2", "RESULT_MISMATCH", id="note-not-falsum"),
    pytest.param(["¬¬P"], "Q ; DNE 1", "RESULT_MISMATCH", id="dne-wrong-result"),
    pytest.param(["P"], "Q ; R 1", "RESULT_MISMATCH", id="r-wrong-result"),
    pytest.param(["P ↔ Q", "P"], "P ; IffE 1,2", "RESULT_MISMATCH", id="iffe-wrong-result"),
])
def test_rule_misuse(premises, last, code):
    outcome = check(premises, "P", proof(premises, last))
    assert outcome["valid"] is False
    assert outcome["lines"][-1]["error"]["code"] == code
    assert all(line["ok"] for line in outcome["lines"][:-1])


def test_mismatch_message_names_what_the_rule_gives():
    outcome = check(["P → Q", "P"], "Q", proof(["P → Q", "P"], "P ; ImpE 1,2"))
    message = outcome["lines"][-1]["error"]["message"]
    assert "gives Q" in message and "not P" in message


# --- request-level errors ---

@pytest.mark.parametrize("text", ["", "   \n \n\t"])
def test_empty_proof(text):
    result = api.check_proof(["P"], "P", text)
    assert result["ok"] is False
    assert result["error"]["code"] == "EMPTY_PROOF"


def test_too_many_lines():
    result = api.check_proof(["P"], "P", "\n".join(["P ; premise"] * (MAX_PROOF_LINES + 1)))
    assert result["ok"] is False
    assert result["error"]["code"] == LIMIT_EXCEEDED


def test_premise_syntax_error_names_its_field():
    result = api.check_proof(["P", "Q ∧"], "P", "P ; premise")
    assert result["ok"] is False
    assert result["error"]["field"] == "premise-2"


def test_conclusion_syntax_error_names_its_field():
    result = api.check_proof(["P"], "→", "P ; premise")
    assert result["ok"] is False
    assert result["error"]["field"] == "conclusion"


def test_too_many_premises():
    result = api.check_proof(["P"] * 21, "P", "P ; premise")
    assert result["ok"] is False
    assert result["error"]["code"] == LIMIT_EXCEEDED


# --- text splitting and the rule table ---

def test_split_proof_text():
    entries = split_proof_text("1. P → Q ; premise\n\nQ ; ImpE 1,2\nno separator")
    assert [(e.formula_text, e.justification) for e in entries] == [
        ("P → Q", "premise"), ("Q", "ImpE 1,2"), ("no separator", None),
    ]


def test_rule_table():
    assert list(RULES) == [
        "premise", "AndI", "AndE", "OrI", "ImpE", "IffE", "NotE", "BotE", "DNE", "R",
    ]
    assert all(rule.statement and isinstance(rule.arity, int) for rule in RULES.values())


# --- the checker is sound, and every rule can be used ---

POOL = ["P", "Q", "¬P", "¬Q", "¬¬P", "P ∧ Q", "P ∨ Q", "P → Q", "P ↔ Q", "⊥"]


@pytest.mark.parametrize("rule_id", [rule for rule in RULES if rule != "premise"])
def test_every_accepted_application_is_semantically_valid(rule_id):
    """Try the rule on every combination from POOL; whatever it accepts must be a valid argument."""
    arity = RULES[rule_id].arity
    refs = ",".join(str(n) for n in range(1, arity + 1))
    accepted = 0
    for cited in itertools.product(POOL, repeat=arity):
        premises = list(dict.fromkeys(cited))
        for result in POOL:
            text = proof(cited, f"{result} ; {rule_id} {refs}")
            outcome = api.check_proof(premises, result, text)
            assert outcome["ok"] is True
            if outcome["lines"][-1]["ok"]:
                accepted += 1
                assert outcome["complete"]
                assert api.valid(premises, result)["valid"], (rule_id, cited, result)
    assert accepted > 0     # the rule can actually be used

