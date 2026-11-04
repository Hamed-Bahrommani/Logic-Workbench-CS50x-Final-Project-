"""Rewriting a formula into negation, conjunctive or disjunctive normal form.

Every change is one application of a named law to one subformula, so a result
is a list of steps a student can check by hand. The rewriter is deterministic:
at each step it looks for the first place a law applies, outermost first and
left before right, and tries the laws of the current phase in a fixed order.
It does not simplify: P ∨ P stays P ∨ P. That keeps each step a single named law.
"""

from dataclasses import dataclass
from typing import Callable, NamedTuple

from logic.nodes import And, Bot, Iff, Imp, Not, Or, Var, node_count

MAX_NODES = 200   # no formula (start, intermediate or final) may be larger
MAX_STEPS = 500   # a second guard; MAX_NODES normally stops a runaway first


class RewriteLimit(Exception):
    """The formula, or an intermediate result, is too large to rewrite."""


class Law(NamedTuple):
    name: str
    statement: str
    apply: Callable   # node -> replacement node, or None if the law does not apply here


# --- the laws ---------------------------------------------------------------

def _iff_elim(f):
    if isinstance(f, Iff):
        return And(Imp(f.left, f.right), Imp(f.right, f.left))
    return None


def _imp_elim(f):
    if isinstance(f, Imp):
        return Or(Not(f.left), f.right)
    return None


def _double_neg(f):
    if isinstance(f, Not) and isinstance(f.child, Not):
        return f.child.child
    return None


def _de_morgan_and(f):
    if isinstance(f, Not) and isinstance(f.child, And):
        return Or(Not(f.child.left), Not(f.child.right))
    return None


def _de_morgan_or(f):
    if isinstance(f, Not) and isinstance(f.child, Or):
        return And(Not(f.child.left), Not(f.child.right))
    return None


def _distribute_or(f):
    if isinstance(f, Or):
        if isinstance(f.left, And):
            return And(Or(f.left.left, f.right), Or(f.left.right, f.right))
        if isinstance(f.right, And):
            return And(Or(f.left, f.right.left), Or(f.left, f.right.right))
    return None


def _distribute_and(f):
    if isinstance(f, And):
        if isinstance(f.left, Or):
            return Or(And(f.left.left, f.right), And(f.left.right, f.right))
        if isinstance(f.right, Or):
            return Or(And(f.left, f.right.left), And(f.left, f.right.right))
    return None


IFF_ELIM = Law("Eliminate ↔", "A ↔ B  ≡  (A → B) ∧ (B → A)", _iff_elim)
IMP_ELIM = Law("Eliminate →", "A → B  ≡  ¬A ∨ B", _imp_elim)
DOUBLE_NEG = Law("Double negation", "¬¬A  ≡  A", _double_neg)
DE_MORGAN_AND = Law("De Morgan (∧)", "¬(A ∧ B)  ≡  ¬A ∨ ¬B", _de_morgan_and)
DE_MORGAN_OR = Law("De Morgan (∨)", "¬(A ∨ B)  ≡  ¬A ∧ ¬B", _de_morgan_or)
DISTRIBUTE_OR = Law(
    "Distribute ∨ over ∧", "A ∨ (B ∧ C)  ≡  (A ∨ B) ∧ (A ∨ C)", _distribute_or
)
DISTRIBUTE_AND = Law(
    "Distribute ∧ over ∨", "A ∧ (B ∨ C)  ≡  (A ∧ B) ∨ (A ∧ C)", _distribute_and
)

_TO_NNF = [IFF_ELIM, IMP_ELIM, DOUBLE_NEG, DE_MORGAN_AND, DE_MORGAN_OR]

# A strategy is a list of phases; each phase runs until none of its laws applies.
STRATEGIES = {
    "nnf": [_TO_NNF],
    "cnf": [_TO_NNF, [DISTRIBUTE_OR]],
    "dnf": [_TO_NNF, [DISTRIBUTE_AND]],
}


# --- recognising the normal forms ----------------------------------------------

def is_literal(f) -> bool:
    """A variable or ⊥, or the negation of one."""
    return isinstance(f, (Var, Bot)) or (
        isinstance(f, Not) and isinstance(f.child, (Var, Bot))
    )


def is_nnf(f) -> bool:
    if is_literal(f):
        return True
    if isinstance(f, (And, Or)):
        return is_nnf(f.left) and is_nnf(f.right)
    return False


def _is_clause(f) -> bool:
    if isinstance(f, Or):
        return _is_clause(f.left) and _is_clause(f.right)
    return is_literal(f)


def _is_term(f) -> bool:
    if isinstance(f, And):
        return _is_term(f.left) and _is_term(f.right)
    return is_literal(f)


def is_cnf(f) -> bool:
    if isinstance(f, And):
        return is_cnf(f.left) and is_cnf(f.right)
    return _is_clause(f)


def is_dnf(f) -> bool:
    if isinstance(f, Or):
        return is_dnf(f.left) and is_dnf(f.right)
    return _is_term(f)


# --- the rewriter -----------------------------------------------------------

@dataclass(frozen=True)
class Step:
    law: Law
    before: object   # the subformula the law was applied to
    after: object    # what it was replaced by
    whole: object    # the entire formula after this step


@dataclass(frozen=True)
class Rewritten:
    final: object
    steps: list


def _rewrite_once(node, laws):
    """Apply the first applicable law at the first place it applies.

    Returns (new tree, law, old subformula, new subformula), or None.
    """
    for law in laws:
        new = law.apply(node)
        if new is not None:
            return new, law, node, new

    if isinstance(node, Not):
        hit = _rewrite_once(node.child, laws)
        if hit is not None:
            return (Not(hit[0]), *hit[1:])
    elif isinstance(node, (And, Or, Imp, Iff)):
        hit = _rewrite_once(node.left, laws)
        if hit is not None:
            return (type(node)(hit[0], node.right), *hit[1:])
        hit = _rewrite_once(node.right, laws)
        if hit is not None:
            return (type(node)(node.left, hit[0]), *hit[1:])
    return None


def rewrite(formula, strategy: str) -> Rewritten:
    """Rewrite `formula` with the named strategy ("nnf", "cnf" or "dnf").

    Raises ValueError for an unknown strategy and RewriteLimit if the formula
    or any intermediate result has more than MAX_NODES nodes.
    """
    phases = STRATEGIES[strategy] if strategy in STRATEGIES else None
    if phases is None:
        raise ValueError(f"unknown strategy {strategy!r}")
    if node_count(formula) > MAX_NODES:
        raise RewriteLimit(
            f"the formula has {node_count(formula)} nodes; the limit is {MAX_NODES}"
        )

    current = formula
    steps: list[Step] = []
    for laws in phases:
        while True:
            hit = _rewrite_once(current, laws)
            if hit is None:
                break
            current, law, old, new = hit
            size = node_count(current)
            if size > MAX_NODES:
                raise RewriteLimit(
                    f"the rewrite grew past {MAX_NODES} nodes after {len(steps) + 1} steps"
                )
            if len(steps) >= MAX_STEPS:
                raise RewriteLimit(f"the rewrite needs more than {MAX_STEPS} steps")
            steps.append(Step(law, old, new, current))
    return Rewritten(current, steps)