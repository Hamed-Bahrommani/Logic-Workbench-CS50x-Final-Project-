import pytest

from logic.errors import LIMIT_EXCEEDED, LimitExceeded
from logic.parser import parse
from logic.truth_table import COMPUTE_LIMIT, DISPLAY_LIMIT, build_truth_table, classify


def table(text):
    return build_truth_table(parse(text))


def many_variables(n, op="∧"):
    """A formula over exactly n variables: v1 op v2 op ... op vn."""
    return f" {op} ".join(f"v{i}" for i in range(1, n + 1))


# --- exact tables ---

def test_conjunction_table():
    t = table("P ∧ Q")
    assert t["variables"] == ["P", "Q"]
    assert [(r["assignment"]["P"], r["assignment"]["Q"], r["value"]) for r in t["rows"]] == [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ]


def test_implication_table_matches_textbook():
    t = table("P → Q")
    assert [r["value"] for r in t["rows"]] == [True, False, True, True]


def test_three_variable_row_order():
    t = table("A ∨ B ∨ C")
    assert [tuple(r["assignment"].values()) for r in t["rows"]] == [
        (True, True, True), (True, True, False), (True, False, True), (True, False, False),
        (False, True, True), (False, True, False), (False, False, True), (False, False, False),
    ]
    assert [r["value"] for r in t["rows"]] == [True] * 7 + [False]


def test_counts():
    t = table("P ∨ Q")
    assert (t["row_count"], t["true_count"]) == (4, 3)


# --- zero variables ---

def test_bottom_has_one_row_and_no_variables():
    t = table("⊥")
    assert t["variables"] == []
    assert t["rows"] == [{"assignment": {}, "value": False}]
    assert t["classification"] == "contradiction"
    assert t["satisfiable"] is False


def test_not_bottom_is_a_tautology():
    t = table("¬⊥")
    assert t["rows"] == [{"assignment": {}, "value": True}]
    assert t["classification"] == "tautology"
    assert t["satisfiable"] is True


# --- classification ---

@pytest.mark.parametrize("text, classification, satisfiable", [
    ("P", "contingency", True),
    ("¬P", "contingency", True),
    ("P ∨ ¬P", "tautology", True),
    ("P ∧ ¬P", "contradiction", False),
    ("P → P", "tautology", True),
    ("P ↔ ¬P", "contradiction", False),
    ("P → (Q → P)", "tautology", True),
    ("P → (Q ∧ ¬R)", "contingency", True),
    ("(P → Q) → P", "contingency", True),
    ("((P → Q) → P) → P", "tautology", True),            # Peirce's law
    ("¬(P ∧ Q) ↔ (¬P ∨ ¬Q)", "tautology", True),         # De Morgan
    ("¬(P ∨ Q) ↔ (¬P ∧ ¬Q)", "tautology", True),         # De Morgan
    ("(P → Q) ↔ (¬Q → ¬P)", "tautology", True),          # contraposition
    ("(P ∧ Q) ∨ R ↔ (P ∨ R) ∧ (Q ∨ R)", "tautology", True),  # distribution
    ("P ∧ ¬P ∧ Q", "contradiction", False),
    ("(P → Q) ∧ P ∧ ¬Q", "contradiction", False),         # modus ponens refuted
    ("⊥ → P", "tautology", True),                         # ex falso
    ("P ∧ ⊥", "contradiction", False),
])
def test_classification(text, classification, satisfiable):
    t = table(text)
    assert t["classification"] == classification
    assert t["satisfiable"] is satisfiable


def test_classify_boundaries():
    assert classify(4, 4) == "tautology"
    assert classify(0, 4) == "contradiction"
    assert classify(1, 4) == "contingency"
    assert classify(3, 4) == "contingency"
    assert classify(1, 1) == "tautology"     # zero-variable ¬⊥
    assert classify(0, 1) == "contradiction"  # zero-variable ⊥


def test_row_values_agree_with_counts():
    t = table("P → (Q ∧ ¬R)")
    assert sum(r["value"] for r in t["rows"]) == t["true_count"] == 5
    assert len(t["rows"]) == t["row_count"] == 8


# --- the spec's example, row by row ---

def test_spec_example_p_implies_q_and_not_r():
    t = table("P → (Q ∧ ¬R)")
    values = {(r["assignment"]["P"], r["assignment"]["Q"], r["assignment"]["R"]): r["value"]
              for r in t["rows"]}
    assert values == {
        (True, True, True): False,
        (True, True, False): True,
        (True, False, True): False,
        (True, False, False): False,
        (False, True, True): True,
        (False, True, False): True,
        (False, False, True): True,
        (False, False, False): True,
    }


# --- limits ---

def test_display_limit_boundary():
    at_limit = build_truth_table(parse(many_variables(DISPLAY_LIMIT)))
    assert at_limit["rows_omitted"] is False
    assert len(at_limit["rows"]) == 2 ** DISPLAY_LIMIT == 256

    over = build_truth_table(parse(many_variables(DISPLAY_LIMIT + 1)))
    assert over["rows_omitted"] is True
    assert "rows" not in over


def test_omitted_rows_still_give_the_full_answer():
    t = build_truth_table(parse(many_variables(DISPLAY_LIMIT + 1)))
    assert t["row_count"] == 2 ** 9
    assert t["true_count"] == 1                      # only the all-true row
    assert t["classification"] == "contingency"
    assert t["satisfiable"] is True

    taut = build_truth_table(parse(many_variables(9, "∨") + " ∨ ¬v1"))
    assert taut["classification"] == "tautology"
    assert taut["rows_omitted"] is True


def test_compute_limit_boundary():
    at_limit = build_truth_table(parse(many_variables(COMPUTE_LIMIT)))
    assert at_limit["row_count"] == 2 ** COMPUTE_LIMIT
    assert at_limit["true_count"] == 1

    with pytest.raises(LimitExceeded) as err:
        build_truth_table(parse(many_variables(COMPUTE_LIMIT + 1)))
    assert err.value.code == LIMIT_EXCEEDED
    assert err.value.limit == COMPUTE_LIMIT
    assert err.value.actual == COMPUTE_LIMIT + 1


def test_limit_counts_distinct_variables_not_occurrences():
    # 39 occurrences, 3 distinct variables: well within limits
    t = table(" ∧ ".join(["A", "B", "C"] * 13))
    assert t["variables"] == ["A", "B", "C"]
    assert t["row_count"] == 8


def test_limits_are_the_documented_values():
    assert (DISPLAY_LIMIT, COMPUTE_LIMIT) == (8, 16)