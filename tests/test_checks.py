import random

import pytest

from logic.checks import MAX_PREMISES, WORK_LIMIT, check_equivalence, check_validity
from logic.errors import LIMIT_EXCEEDED, LimitExceeded
from logic.evaluate import assignments, evaluate, variables
from logic.nodes import And, Bot, Iff, Imp, Not, Or, Var, node_count
from logic.parser import parse
from logic.truth_table import COMPUTE_LIMIT


def equivalence(left, right):
    return check_equivalence(parse(left), parse(right))


def validity(premises, conclusion):
    return check_validity([parse(p) for p in premises], parse(conclusion))


def chain(prefix, count):
    """prefix0 ∧ prefix1 ∧ ... : a formula over exactly `count` variables."""
    return " ∧ ".join(f"{prefix}{i}" for i in range(count))


def random_formula(rng, height, names):
    if height <= 1 or rng.random() < 0.2:
        return rng.choice([Var(n) for n in names] + [Bot()])
    if rng.random() < 0.2:
        return Not(random_formula(rng, height - 1, names))
    node_class = rng.choice([And, Or, Imp, Iff])
    return node_class(random_formula(rng, height - 1, names),
                      random_formula(rng, height - 1, names))


# --- node_count ---

@pytest.mark.parametrize("text, expected", [
    ("P", 1),
    ("⊥", 1),
    ("¬¬P", 3),
    ("P ∧ (Q → ¬R)", 6),
])
def test_node_count(text, expected):
    assert node_count(parse(text)) == expected


# --- equivalence ---

EQUIVALENT = [
    ("P → Q", "¬P ∨ Q"),
    ("¬(P ∧ Q)", "¬P ∨ ¬Q"),
    ("¬(P ∨ Q)", "¬P ∧ ¬Q"),
    ("P → Q", "¬Q → ¬P"),
    ("P ↔ Q", "(P → Q) ∧ (Q → P)"),
    ("¬¬P", "P"),
    ("P ∧ (Q ∨ R)", "(P ∧ Q) ∨ (P ∧ R)"),
    ("P ∨ (Q ∧ R)", "(P ∨ Q) ∧ (P ∨ R)"),
    ("P → (Q → R)", "(P ∧ Q) → R"),
    ("P ∧ P", "P"),
    ("P ∨ ⊥", "P"),
    ("P ∧ ¬P", "⊥"),       # different variable sets, same meaning
    ("P ∨ ¬P", "¬⊥"),
]


@pytest.mark.parametrize("left, right", EQUIVALENT)
def test_known_equivalences(left, right):
    result = equivalence(left, right)
    assert result["equivalent"] is True
    assert result["distinguishing"] is None
    assert equivalence(right, left)["equivalent"] is True


# (left, right, first differing assignment, left value there, right value there)
NOT_EQUIVALENT = [
    ("P → Q", "Q → P", {"P": True, "Q": False}, False, True),
    ("P ∧ Q", "P ∨ Q", {"P": True, "Q": False}, False, True),
    ("P", "Q", {"P": True, "Q": False}, True, False),
    ("P", "⊥", {"P": True}, True, False),
    ("P", "P ∧ Q", {"P": True, "Q": False}, True, False),   # the assignment covers both variables
    ("P → (Q → R)", "(P → Q) → R", {"P": False, "Q": True, "R": False}, True, False),
]


@pytest.mark.parametrize("left, right, assignment, left_value, right_value", NOT_EQUIVALENT)
def test_non_equivalences_report_the_first_difference(left, right, assignment, left_value, right_value):
    result = equivalence(left, right)
    assert result["equivalent"] is False
    assert result["distinguishing"] == {
        "assignment": assignment, "left_value": left_value, "right_value": right_value,
    }


@pytest.mark.parametrize("left, right, assignment, left_value, right_value", NOT_EQUIVALENT)
def test_swapping_the_sides_swaps_the_values(left, right, assignment, left_value, right_value):
    result = equivalence(right, left)
    assert result["distinguishing"] == {
        "assignment": assignment, "left_value": right_value, "right_value": left_value,
    }


def test_zero_variable_equivalence():
    same = equivalence("⊥", "¬¬⊥")
    assert same["equivalent"] is True
    assert same["variables"] == []

    different = equivalence("⊥", "¬⊥")
    assert different["equivalent"] is False
    assert different["distinguishing"] == {"assignment": {}, "left_value": False, "right_value": True}


def test_equivalence_matches_brute_force_on_random_pairs():
    rng = random.Random(5)
    names = ["P", "Q", "R"]
    for _ in range(300):
        a = random_formula(rng, 4, names)
        b = random_formula(rng, 4, names)
        result = check_equivalence(a, b)

        union = sorted(set(variables(a)) | set(variables(b)))
        first_difference = next(
            (s for s in assignments(union) if evaluate(a, s) != evaluate(b, s)), None
        )
        assert result["variables"] == union
        if first_difference is None:
            assert result["equivalent"] is True
            assert result["distinguishing"] is None
        else:
            assert result["equivalent"] is False
            assert result["distinguishing"] == {
                "assignment": first_difference,
                "left_value": evaluate(a, first_difference),
                "right_value": evaluate(b, first_difference),
            }


def test_equivalence_variable_limit():
    with pytest.raises(LimitExceeded) as err:
        check_equivalence(parse(chain("a", 9)), parse(chain("b", 8)))   # 9 + 8 = 17 variables
    assert err.value.code == LIMIT_EXCEEDED
    assert err.value.limit == COMPUTE_LIMIT
    assert err.value.actual == 17


def test_equivalence_accepts_the_variable_limit():
    result = check_equivalence(parse(chain("a", 8)), parse(chain("b", 8)))   # exactly 16
    assert result["equivalent"] is False
    assert len(result["variables"]) == COMPUTE_LIMIT


# --- validity ---

VALID = [
    (["P → Q", "P"], "Q"),                       # modus ponens
    (["P → Q", "¬Q"], "¬P"),                     # modus tollens
    (["P ∨ Q", "¬P"], "Q"),                      # disjunctive syllogism
    (["P → Q", "Q → R"], "P → R"),               # hypothetical syllogism
    (["P ∧ Q"], "P"),
    (["P"], "P ∨ Q"),
    ([], "P ∨ ¬P"),                              # no premises: the conclusion is a tautology
    (["P → Q", "R → Q", "P ∨ R"], "Q"),          # proof by cases
    (["P ∧ ¬P"], "Q"),                           # explosion
    (["P"], "P"),
    ([], "((P → Q) → P) → P"),                   # Peirce's law
    (["P ↔ Q", "P"], "Q"),
    (["¬(P ∧ Q)", "P"], "¬Q"),
]


@pytest.mark.parametrize("premises, conclusion", VALID)
def test_valid_arguments(premises, conclusion):
    result = validity(premises, conclusion)
    assert result["valid"] is True
    assert result["countermodel"] is None


# (premises, conclusion, the first countermodel's assignment)
INVALID = [
    (["P → Q", "Q"], "P", {"P": False, "Q": True}),               # affirming the consequent
    (["P → Q", "¬P"], "¬Q", {"P": False, "Q": True}),             # denying the antecedent
    (["P ∨ Q"], "P", {"P": False, "Q": True}),
    ([], "P", {"P": False}),
    (["P"], "Q", {"P": True, "Q": False}),
    (["P → Q"], "Q → P", {"P": False, "Q": True}),                # the converse
    (["P"], "Q ∨ R", {"P": True, "Q": False, "R": False}),
]


@pytest.mark.parametrize("premises, conclusion, assignment", INVALID)
def test_invalid_arguments_report_the_first_countermodel(premises, conclusion, assignment):
    result = validity(premises, conclusion)
    assert result["valid"] is False
    assert result["vacuous"] is False
    assert result["countermodel"] == {
        "assignment": assignment,
        "premise_values": [True] * len(premises),
        "conclusion_value": False,
    }


@pytest.mark.parametrize("premises, conclusion", [
    (["P", "¬P"], "Q"),
    (["P ∧ ¬P"], "⊥"),
    (["⊥"], "P"),
])
def test_vacuous_validity(premises, conclusion):
    result = validity(premises, conclusion)
    assert result["valid"] is True
    assert result["vacuous"] is True


@pytest.mark.parametrize("premises, conclusion", [
    (["P"], "P"),
    ([], "P ∨ ¬P"),
    (["P → Q", "P"], "Q"),
])
def test_non_vacuous_validity(premises, conclusion):
    result = validity(premises, conclusion)
    assert result["valid"] is True
    assert result["vacuous"] is False


def test_zero_variable_arguments():
    assert validity([], "¬⊥")["valid"] is True

    result = validity([], "⊥")
    assert result["valid"] is False
    assert result["variables"] == []
    assert result["countermodel"] == {
        "assignment": {}, "premise_values": [], "conclusion_value": False,
    }


def test_countermodel_assignment_covers_every_variable():
    result = validity(["P"], "Q ∨ R")
    assert result["variables"] == ["P", "Q", "R"]
    assert sorted(result["countermodel"]["assignment"]) == ["P", "Q", "R"]


def test_validity_matches_brute_force_on_random_arguments():
    rng = random.Random(9)
    names = ["P", "Q", "R"]
    for _ in range(300):
        premises = [random_formula(rng, 3, names) for _ in range(rng.randint(0, 3))]
        conclusion = random_formula(rng, 3, names)
        result = check_validity(premises, conclusion)

        union = sorted(set().union(*(variables(f) for f in [*premises, conclusion])))
        models = [s for s in assignments(union) if all(evaluate(p, s) for p in premises)]
        counter = next((s for s in models if not evaluate(conclusion, s)), None)

        assert result["variables"] == union
        assert result["valid"] is (counter is None)
        assert result["vacuous"] is (counter is None and not models)
        if counter is None:
            assert result["countermodel"] is None
        else:
            assert result["countermodel"]["assignment"] == counter
            assert result["countermodel"]["premise_values"] == [True] * len(premises)
            assert result["countermodel"]["conclusion_value"] is False


def test_too_many_premises():
    with pytest.raises(LimitExceeded) as err:
        check_validity([Var("P")] * (MAX_PREMISES + 1), Var("P"))
    assert err.value.code == LIMIT_EXCEEDED
    assert err.value.limit == MAX_PREMISES
    assert err.value.actual == MAX_PREMISES + 1


def test_the_maximum_number_of_premises_is_accepted():
    result = check_validity([Var("P")] * MAX_PREMISES, Var("P"))
    assert result["valid"] is True


def test_validity_variable_limit():
    with pytest.raises(LimitExceeded) as err:
        check_validity([parse(chain("a", 9))], parse(chain("b", 8)))
    assert err.value.limit == COMPUTE_LIMIT
    assert err.value.actual == 17


def test_work_limit():
    big = parse(chain("v", 16))                      # 16 variables, 31 nodes
    with pytest.raises(LimitExceeded) as err:
        check_validity([big] * 6, Var("v0"))         # 6 * 31 + 1 = 187 nodes in all
    assert err.value.code == LIMIT_EXCEEDED
    assert err.value.limit == WORK_LIMIT
    assert err.value.actual == 65536 * 187


def test_limits_are_the_documented_values():
    assert (MAX_PREMISES, WORK_LIMIT, COMPUTE_LIMIT) == (20, 10_000_000, 16)