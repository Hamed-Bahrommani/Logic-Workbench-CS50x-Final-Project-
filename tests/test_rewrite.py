import random
from functools import reduce

import pytest

from logic import api
from logic.checks import check_equivalence
from logic.errors import LIMIT_EXCEEDED
from logic.nodes import And, Bot, Iff, Imp, Not, Or, Var, node_count
from logic.parser import parse
from logic.rewrite import (
    DE_MORGAN_AND, DE_MORGAN_OR, DISTRIBUTE_AND, DISTRIBUTE_OR, DOUBLE_NEG,
    IFF_ELIM, IMP_ELIM, MAX_NODES, STRATEGIES, RewriteLimit, is_cnf, is_dnf,
    is_nnf, rewrite,
)


# --- each law on its own ---

@pytest.mark.parametrize("law, before, after", [
    pytest.param(IFF_ELIM, "P ↔ Q", "(P → Q) ∧ (Q → P)", id="iff"),
    pytest.param(IMP_ELIM, "P → Q", "¬P ∨ Q", id="imp"),
    pytest.param(DOUBLE_NEG, "¬¬P", "P", id="double-negation"),
    pytest.param(DE_MORGAN_AND, "¬(P ∧ Q)", "¬P ∨ ¬Q", id="de-morgan-and"),
    pytest.param(DE_MORGAN_OR, "¬(P ∨ Q)", "¬P ∧ ¬Q", id="de-morgan-or"),
    pytest.param(DISTRIBUTE_OR, "(P ∧ Q) ∨ R", "(P ∨ R) ∧ (Q ∨ R)", id="dist-or-left"),
    pytest.param(DISTRIBUTE_OR, "P ∨ (Q ∧ R)", "(P ∨ Q) ∧ (P ∨ R)", id="dist-or-right"),
    pytest.param(DISTRIBUTE_AND, "(P ∨ Q) ∧ R", "(P ∧ R) ∨ (Q ∧ R)", id="dist-and-left"),
    pytest.param(DISTRIBUTE_AND, "P ∧ (Q ∨ R)", "(P ∧ Q) ∨ (P ∧ R)", id="dist-and-right"),
])
def test_law_application(law, before, after):
    assert law.apply(parse(before)) == parse(after)


@pytest.mark.parametrize("law", [
    IFF_ELIM, IMP_ELIM, DOUBLE_NEG, DE_MORGAN_AND, DE_MORGAN_OR,
    DISTRIBUTE_OR, DISTRIBUTE_AND,
], ids=lambda law: law.name)
def test_a_law_does_not_apply_to_a_variable(law):
    assert law.apply(Var("P")) is None


# --- whole rewrites, worked out by hand ---

@pytest.mark.parametrize("strategy, text, laws, final", [
    pytest.param("nnf", "P → Q", [IMP_ELIM], "¬P ∨ Q", id="nnf-implication"),
    pytest.param("nnf", "¬(P → Q)", [IMP_ELIM, DE_MORGAN_OR, DOUBLE_NEG], "P ∧ ¬Q",
                 id="nnf-negated-implication"),
    pytest.param("nnf", "P ↔ Q", [IFF_ELIM, IMP_ELIM, IMP_ELIM], "(¬P ∨ Q) ∧ (¬Q ∨ P)",
                 id="nnf-biconditional"),
    pytest.param("nnf", "P ∧ ¬Q", [], "P ∧ ¬Q", id="nnf-already"),
    pytest.param("cnf", "¬(P ∧ Q)", [DE_MORGAN_AND], "¬P ∨ ¬Q", id="cnf-de-morgan"),
    pytest.param("cnf", "(P ∧ Q) ∨ R", [DISTRIBUTE_OR], "(P ∨ R) ∧ (Q ∨ R)", id="cnf-left"),
    pytest.param("cnf", "P ∨ (Q ∧ R)", [DISTRIBUTE_OR], "(P ∨ Q) ∧ (P ∨ R)", id="cnf-right"),
    pytest.param("cnf", "(P ∧ Q) ∨ (R ∧ S)", [DISTRIBUTE_OR] * 3,
                 "((P ∨ R) ∧ (P ∨ S)) ∧ ((Q ∨ R) ∧ (Q ∨ S))", id="cnf-two-by-two"),
    pytest.param("dnf", "(P ∨ Q) ∧ R", [DISTRIBUTE_AND], "(P ∧ R) ∨ (Q ∧ R)", id="dnf-left"),
])
def test_worked_rewrites(strategy, text, laws, final):
    outcome = rewrite(parse(text), strategy)
    assert [step.law for step in outcome.steps] == laws
    assert outcome.final == parse(final)


# --- the normal-form recognisers ---

@pytest.mark.parametrize("text, nnf, cnf, dnf", [
    pytest.param("P", True, True, True, id="variable"),
    pytest.param("¬P", True, True, True, id="negated-variable"),
    pytest.param("¬⊥", True, True, True, id="negated-falsum"),
    pytest.param("P ∧ Q", True, True, True, id="conjunction"),
    pytest.param("P ∨ Q", True, True, True, id="disjunction"),
    pytest.param("(P ∨ Q) ∧ R", True, True, False, id="clause-and-literal"),
    pytest.param("(P ∧ Q) ∨ R", True, False, True, id="term-or-literal"),
    pytest.param("P ∨ (Q ∧ R)", True, False, True, id="or-over-and"),
    pytest.param("(P ∨ Q) ∧ (¬P ∨ R)", True, True, False, id="two-clauses"),
    pytest.param("P ∧ (Q ∨ (R ∧ S))", True, False, False, id="neither"),
    pytest.param("¬(P ∧ Q)", False, False, False, id="negated-conjunction"),
    pytest.param("P → Q", False, False, False, id="implication"),
    pytest.param("¬¬P", False, False, False, id="double-negation"),
])
def test_normal_form_recognisers(text, nnf, cnf, dnf):
    formula = parse(text)
    assert (is_nnf(formula), is_cnf(formula), is_dnf(formula)) == (nnf, cnf, dnf)


# --- properties on random formulas ---

def random_formula(rng, depth):
    if depth == 0 or rng.random() < 0.2:
        return rng.choice([Var("P"), Var("Q"), Var("R"), Bot()])
    kind = rng.choice(["not", "and", "or", "imp", "iff"])
    if kind == "not":
        return Not(random_formula(rng, depth - 1))
    node = {"and": And, "or": Or, "imp": Imp, "iff": Iff}[kind]
    return node(random_formula(rng, depth - 1), random_formula(rng, depth - 1))


RECOGNISER = {"nnf": is_nnf, "cnf": is_cnf, "dnf": is_dnf}


@pytest.mark.parametrize("strategy", sorted(STRATEGIES))
def test_random_formulas_reach_the_form_and_stay_equivalent(strategy):
    rng = random.Random(2026)
    checked = 0
    for _ in range(300):
        formula = random_formula(rng, 3)
        try:
            outcome = rewrite(formula, strategy)
        except RewriteLimit:
            continue
        checked += 1
        assert RECOGNISER[strategy](outcome.final)
        # every intermediate formula means the same as the start
        for step in outcome.steps:
            assert check_equivalence(formula, step.whole)["equivalent"]
        assert (outcome.steps[-1].whole if outcome.steps else formula) == outcome.final
    assert checked >= 150


# --- limits ---

def test_start_formula_over_the_node_limit_is_refused():
    big = reduce(And, [Var(f"v{i}") for i in range(101)])
    assert node_count(big) > MAX_NODES
    with pytest.raises(RewriteLimit):
        rewrite(big, "nnf")


def test_blow_up_during_distribution_is_stopped():
    clauses = " ∧ ".join(f"(a{i} ∨ b{i})" for i in range(8))   # 2^8 terms as a DNF
    with pytest.raises(RewriteLimit):
        rewrite(parse(clauses), "dnf")


# --- the API ---

def test_api_payload_for_a_simple_rewrite():
    result = api.normal_form("P → Q", "nnf")
    assert result["ok"] is True
    assert result["strategy"] == "nnf"
    assert result["already"] is False
    assert result["final"] == {"canonical": "¬P ∨ Q", "display": "¬P ∨ Q"}
    [step] = result["steps"]
    assert step["law"] == "Eliminate →"
    assert step["before"] == "P → Q"
    assert step["after"] == "¬P ∨ Q"
    assert step["whole"] == "¬P ∨ Q"
    assert step["statement"]


def test_api_formula_already_in_the_form():
    result = api.normal_form("P ∧ ¬Q", "cnf")
    assert result["ok"] is True
    assert result["already"] is True
    assert result["steps"] == []
    assert result["final"] == result["start"]


def test_api_final_formula_is_equivalent_to_the_start():
    result = api.normal_form("¬(P ↔ Q) → R", "cnf")
    assert result["ok"] is True
    check = api.equivalent(result["start"]["canonical"], result["final"]["canonical"])
    assert check["ok"] and check["equivalent"]


def test_api_unknown_strategy():
    result = api.normal_form("P", "xyz")
    assert result["ok"] is False
    assert result["error"]["code"] == "UNKNOWN_STRATEGY"


def test_api_parse_errors_pass_through():
    result = api.normal_form("P ∧", "cnf")
    assert result["ok"] is False
    assert result["error"]["code"] == "UNEXPECTED_END"
    assert result["error"]["position"] == 3


def test_api_limit_is_a_clean_error():
    clauses = " ∧ ".join(f"(a{i} ∨ b{i})" for i in range(8))
    result = api.normal_form(clauses, "dnf")
    assert result["ok"] is False
    assert result["error"]["code"] == LIMIT_EXCEEDED


@pytest.mark.parametrize("strategy", ["nnf", "cnf", "dnf"])
def test_api_accepts_every_strategy(strategy):
    assert api.normal_form("P ↔ (Q ∨ R)", strategy)["ok"] is True
