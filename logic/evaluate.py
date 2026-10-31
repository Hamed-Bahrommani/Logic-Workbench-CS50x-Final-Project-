"""Evaluator: what a formula means under a truth assignment (the semantics)."""

from collections.abc import Iterator
from itertools import product

from .nodes import And, Bot, Formula, Iff, Imp, Not, Or, Var

Assignment = dict[str, bool]


def variables(formula: Formula) -> list[str]:
    """The distinct variable names in `formula`, sorted.

    Sorting is Python's default string order, which is case-sensitive:
    "P" comes before "p". ⊥ is a constant, not a variable.
    """
    found: set[str] = set()
    _collect(formula, found)
    return sorted(found)


def _collect(formula: Formula, found: set[str]) -> None:
    if isinstance(formula, Var):
        found.add(formula.name)
    elif isinstance(formula, Bot):
        pass
    elif isinstance(formula, Not):
        _collect(formula.child, found)
    else:
        _collect(formula.left, found)
        _collect(formula.right, found)


def evaluate(formula: Formula, assignment: Assignment) -> bool:
    """The truth value of `formula` when each variable takes its value from `assignment`.

    Raises KeyError if a variable of the formula is missing from the assignment.
    Extra variables in the assignment are ignored.
    """
    if isinstance(formula, Var):
        return assignment[formula.name]
    if isinstance(formula, Bot):
        return False
    if isinstance(formula, Not):
        return not evaluate(formula.child, assignment)

    if not isinstance(formula, (And, Or, Imp, Iff)):
        raise TypeError(f"not a formula: {formula!r}")

    # Both sides are always evaluated (no short-circuiting), so a missing
    # variable is reported the same way whatever the other side's value is.
    left = evaluate(formula.left, assignment)
    right = evaluate(formula.right, assignment)
    if isinstance(formula, And):
        return left and right
    if isinstance(formula, Or):
        return left or right
    if isinstance(formula, Imp):
        return (not left) or right
    return left == right  # Iff


def assignments(names: list[str]) -> Iterator[Assignment]:
    """Every assignment to `names`, in textbook order.

    True comes before False, and the first name changes slowest, so for
    ["P", "Q"] the order is TT, TF, FT, FF. With no names there is exactly one
    assignment: the empty one.
    """
    for values in product((True, False), repeat=len(names)):
        yield dict(zip(names, values))