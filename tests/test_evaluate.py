import random

import pytest

from logic.evaluate import assignments, evaluate, variables
from logic.nodes import And, Bot, Iff, Imp, Not, Or, Var
from logic.parser import parse

P, Q, R = Var("P"), Var("Q"), Var("R")
T, F = True, False


# --- connectives: the full truth table of each, written out by hand ---

@pytest.mark.parametrize("node_class, table", [
    (And, {(T, T): T, (T, F): F, (F, T): F, (F, F): F}),
    (Or,  {(T, T): T, (T, F): T, (F, T): T, (F, F): F}),
    (Imp, {(T, T): T, (T, F): F, (F, T): T, (F, F): T}),
    (Iff, {(T, T): T, (T, F): F, (F, T): F, (F, F): T}),
])
def test_binary_connectives(node_class, table):
    for (p, q), expected in table.items():
        assert evaluate(node_class(P, Q), {"P": p, "Q": q}) is expected, (p, q)


def test_negation():
    assert evaluate(Not(P), {"P": True}) is False
    assert evaluate(Not(P), {"P": False}) is True


def test_bottom_is_false_and_needs_no_assignment():
    assert evaluate(Bot(), {}) is False
    assert evaluate(Not(Bot()), {}) is True
    assert evaluate(Imp(Bot(), P), {"P": False}) is True   # ⊥ → anything is true


def test_results_are_real_booleans():
    for formula in [P, Not(P), And(P, Q), Or(P, Q), Imp(P, Q), Iff(P, Q), Bot()]:
        assert type(evaluate(formula, {"P": True, "Q": False})) is bool


def test_extra_variables_in_assignment_are_ignored():
    assert evaluate(P, {"P": True, "Z": False}) is True


def test_missing_variable_raises_key_error():
    with pytest.raises(KeyError):
        evaluate(And(P, Q), {"P": True})
    # reported even when the other side already decides the answer
    with pytest.raises(KeyError):
        evaluate(And(P, Q), {"Q": False})
    with pytest.raises(KeyError):
        evaluate(Or(P, Q), {"P": True})
    with pytest.raises(KeyError):
        evaluate(And(P, Q), {"P": False})
    with pytest.raises(KeyError):
        evaluate(Imp(P, Q), {"P": False})


def test_evaluate_rejects_non_formulas():
    with pytest.raises(TypeError):
        evaluate("P", {"P": True})


# --- variables ---

@pytest.mark.parametrize("text, expected", [
    ("P", ["P"]),
    ("⊥", []),
    ("¬⊥", []),
    ("P ∧ P", ["P"]),                      # distinct
    ("Q ∧ P", ["P", "Q"]),                 # sorted
    ("P → (Q → P)", ["P", "Q"]),
    ("rain ∨ P ∨ Q1", ["P", "Q1", "rain"]),
    ("p ∧ P", ["P", "p"]),                 # case-sensitive: uppercase sorts first
    ("x10 ∧ x2", ["x10", "x2"]),           # plain string order, not numeric
])
def test_variables(text, expected):
    assert variables(parse(text)) == expected


# --- assignments: textbook order ---

def test_assignments_no_variables_gives_one_empty_assignment():
    assert list(assignments([])) == [{}]


def test_assignments_one_variable():
    assert list(assignments(["P"])) == [{"P": T}, {"P": F}]


def test_assignments_two_variables_true_first_first_name_slowest():
    assert [(a["P"], a["Q"]) for a in assignments(["P", "Q"])] == [
        (T, T), (T, F), (F, T), (F, F),
    ]


def test_assignments_three_variables():
    assert [tuple(a.values()) for a in assignments(["A", "B", "C"])] == [
        (T, T, T), (T, T, F), (T, F, T), (T, F, F),
        (F, T, T), (F, T, F), (F, F, T), (F, F, F),
    ]


def test_assignments_count_and_distinctness():
    rows = list(assignments(["A", "B", "C", "D", "E"]))
    assert len(rows) == 32
    assert len({tuple(r.items()) for r in rows}) == 32


# --- independent oracle: a second evaluator built from lookup tables ---

_AND = {(T, T): T, (T, F): F, (F, T): F, (F, F): F}
_OR = {(T, T): T, (T, F): T, (F, T): T, (F, F): F}
_IMP = {(T, T): T, (T, F): F, (F, T): T, (F, F): T}
_IFF = {(T, T): T, (T, F): F, (F, T): F, (F, F): T}
_TABLES = {And: _AND, Or: _OR, Imp: _IMP, Iff: _IFF}


def reference(formula, assignment):
    kind = type(formula)
    if kind is Var:
        return assignment[formula.name]
    if kind is Bot:
        return F
    if kind is Not:
        return {T: F, F: T}[reference(formula.child, assignment)]
    return _TABLES[kind][(reference(formula.left, assignment),
                          reference(formula.right, assignment))]


def random_formula(rng, height, names):
    if height <= 1 or rng.random() < 0.2:
        return rng.choice([Var(n) for n in names] + [Bot()])
    if rng.random() < 0.2:
        return Not(random_formula(rng, height - 1, names))
    node_class = rng.choice([And, Or, Imp, Iff])
    return node_class(random_formula(rng, height - 1, names),
                      random_formula(rng, height - 1, names))


def test_evaluator_agrees_with_reference_on_random_formulas():
    rng = random.Random(7)
    names = ["P", "Q", "R", "S"]
    for _ in range(500):
        formula = random_formula(rng, 5, names)
        for assignment in assignments(names):
            assert evaluate(formula, assignment) is reference(formula, assignment)