import random

import pytest

from logic.nodes import And, Bot, Iff, Imp, Not, Or, Var
from logic.parser import parse
from logic.printer import to_string

P, Q, R = Var("P"), Var("Q"), Var("R")

# (input, canonical output). The printer is AST-preserving: it emits parentheses
# exactly where re-parsing would otherwise build a different tree.
CANONICAL_CASES = [
    # associativity is preserved, redundant parentheses are dropped
    ("P ∧ Q ∧ R", "P ∧ Q ∧ R"),
    ("(P ∧ Q) ∧ R", "P ∧ Q ∧ R"),
    ("P ∧ (Q ∧ R)", "P ∧ (Q ∧ R)"),
    ("P ∨ Q ∨ R", "P ∨ Q ∨ R"),
    ("P ∨ (Q ∨ R)", "P ∨ (Q ∨ R)"),
    ("P → Q → R", "P → Q → R"),
    ("P → (Q → R)", "P → Q → R"),
    ("(P → Q) → R", "(P → Q) → R"),
    ("(P ↔ Q) ↔ R", "(P ↔ Q) ↔ R"),
    ("P ↔ (Q ↔ R)", "P ↔ (Q ↔ R)"),
    # precedence
    ("(P ∨ Q) ∧ R", "(P ∨ Q) ∧ R"),
    ("P ∨ (Q ∧ R)", "P ∨ Q ∧ R"),
    ("(P ∧ Q) → (R ∨ S)", "P ∧ Q → R ∨ S"),
    ("P ↔ (Q → R)", "P ↔ Q → R"),
    ("(P → Q) ↔ R", "P → Q ↔ R"),
    ("(P ↔ Q) → R", "(P ↔ Q) → R"),
    # negation and constants
    ("¬¬P", "¬¬P"),
    ("¬(¬P)", "¬¬P"),
    ("¬(P)", "¬P"),
    ("¬(P ∧ Q)", "¬(P ∧ Q)"),
    ("¬(P ↔ Q)", "¬(P ↔ Q)"),
    ("¬P ∧ Q", "¬P ∧ Q"),
    ("¬⊥", "¬⊥"),
    ("(P)", "P"),
    ("((P ∧ Q))", "P ∧ Q"),
    # ASCII aliases and spacing are normalised
    ("~P & Q", "¬P ∧ Q"),
    ("!P | Q", "¬P ∨ Q"),
    ("P -> Q", "P → Q"),
    ("P <-> Q", "P ↔ Q"),
    ("_|_", "⊥"),
    ("rain -> Q1", "rain → Q1"),
    ("P↔Q→R", "P ↔ Q → R"),
]


@pytest.mark.parametrize("text, expected", CANONICAL_CASES)
def test_canonical_output(text, expected):
    assert to_string(parse(text)) == expected


@pytest.mark.parametrize("text, _expected", CANONICAL_CASES)
def test_round_trip_preserves_ast(text, _expected):
    ast = parse(text)
    assert parse(to_string(ast)) == ast


@pytest.mark.parametrize("text, _expected", CANONICAL_CASES)
def test_printing_is_idempotent(text, _expected):
    once = to_string(parse(text))
    assert to_string(parse(once)) == once


def test_printer_on_hand_built_trees():
    assert to_string(And(P, And(Q, R))) == "P ∧ (Q ∧ R)"
    assert to_string(And(And(P, Q), R)) == "P ∧ Q ∧ R"
    assert to_string(Imp(Imp(P, Q), R)) == "(P → Q) → R"
    assert to_string(Imp(P, Imp(Q, R))) == "P → Q → R"
    assert to_string(Not(Not(Bot()))) == "¬¬⊥"


def test_different_trees_never_print_the_same():
    assert to_string(And(And(P, Q), R)) != to_string(And(P, And(Q, R)))
    assert to_string(Or(And(P, Q), R)) != to_string(And(P, Or(Q, R)))


# --- randomized round trip over trees (not strings) ---

ATOMS = [Var("P"), Var("Q"), Var("R"), Var("rain"), Var("Q1"), Bot()]
BINARY = [And, Or, Imp, Iff]


def random_formula(rng, height):
    if height <= 1 or rng.random() < 0.2:
        return rng.choice(ATOMS)
    if rng.random() < 0.2:
        return Not(random_formula(rng, height - 1))
    node_class = rng.choice(BINARY)
    return node_class(random_formula(rng, height - 1), random_formula(rng, height - 1))


def test_round_trip_on_random_trees():
    rng = random.Random(2026)  # fixed seed: failures are reproducible
    for _ in range(3000):
        formula = random_formula(rng, 6)
        assert parse(to_string(formula)) == formula, to_string(formula)

# --- explicit-grouping mode (the web page uses this) ---

EXPLICIT_CASES = [
    ("P", "P"),
    ("⊥", "⊥"),
    ("¬⊥", "¬⊥"),
    ("¬¬P", "¬¬P"),
    ("¬P ∧ Q", "¬P ∧ Q"),
    ("¬(P ∧ Q)", "¬(P ∧ Q)"),
    ("P → (Q ∧ ¬R)", "P → (Q ∧ ¬R)"),
    ("P ∨ Q ∧ R", "P ∨ (Q ∧ R)"),
    ("P ∧ Q → R ∨ S", "(P ∧ Q) → (R ∨ S)"),
    ("P ↔ Q → R", "P ↔ (Q → R)"),
    ("P → Q ↔ R", "(P → Q) ↔ R"),
    ("(P ∨ Q) ∧ R", "(P ∨ Q) ∧ R"),
    ("P ∧ Q ∨ R ∧ S ∨ U", "(P ∧ Q) ∨ (R ∧ S) ∨ U"),
    ("P ∧ Q ∧ R", "P ∧ Q ∧ R"),              # same-operator chains keep their associativity
    ("P ∧ (Q ∧ R)", "P ∧ (Q ∧ R)"),
    ("P → Q → R", "P → Q → R"),
    ("(P → Q) → R", "(P → Q) → R"),
    ("(P ↔ Q) ↔ R", "(P ↔ Q) ↔ R"),
    ("¬(P ∨ Q) ↔ ¬P ∧ ¬Q", "¬(P ∨ Q) ↔ (¬P ∧ ¬Q)"),
    ("(P ∧ Q) ∨ R ↔ (P ∨ R) ∧ (Q ∨ R)", "((P ∧ Q) ∨ R) ↔ ((P ∨ R) ∧ (Q ∨ R))"),
]


@pytest.mark.parametrize("text, expected", EXPLICIT_CASES)
def test_explicit_output_and_round_trip(text, expected):
    ast = parse(text)
    printed = to_string(ast, explicit=True)
    assert printed == expected
    assert parse(printed) == ast          # the extra parentheses never change the tree


def test_explicit_round_trip_on_random_trees():
    rng = random.Random(2027)
    for _ in range(3000):
        formula = random_formula(rng, 6)
        assert parse(to_string(formula, explicit=True)) == formula, to_string(formula)


def test_explicit_mode_only_ever_adds_parentheses():
    rng = random.Random(11)
    for _ in range(1000):
        formula = random_formula(rng, 6)
        minimal = to_string(formula)
        explicit = to_string(formula, explicit=True)
        assert explicit.count("(") >= minimal.count("(")
        assert explicit.replace("(", "").replace(")", "") == minimal.replace("(", "").replace(")", "")