"""Checks that compare several formulas at once: equivalence and argument validity.

Both work the way a truth table does: try every assignment, in textbook order,
and stop at the first one that settles the question. Because the order is
fixed, the "first" counterexample is always the same one.
"""
from .errors import LimitExceeded
from .evaluate import assignments, evaluate, variables
from .nodes import Formula, node_count
from .truth_table import COMPUTE_LIMIT

# An argument may have at most this many premises.
MAX_PREMISES = 20

# Checking tries 2**n assignments, evaluating every node of every formula on
# each. The variable limit alone does not bound that cost (many large premises
# over 16 variables would be slow), so the product is capped too.
WORK_LIMIT = 10_000_000


def check_equivalence(left: Formula, right: Formula) -> dict:
    """Do `left` and `right` have the same truth value under every assignment?

    Returns variables (the union, sorted), equivalent, and distinguishing: the
    first assignment where they differ as
    {"assignment": {...}, "left_value": bool, "right_value": bool}, or None.
    """
    names = _all_variables([left, right])
    _check_size(names, [left, right])

    for assignment in assignments(names):
        left_value = evaluate(left, assignment)
        right_value = evaluate(right, assignment)
        if left_value != right_value:
            return {
                "variables": names,
                "equivalent": False,
                "distinguishing": {
                    "assignment": assignment,
                    "left_value": left_value,
                    "right_value": right_value,
                },
            }
    return {"variables": names, "equivalent": True, "distinguishing": None}


def check_validity(premises: list[Formula], conclusion: Formula) -> dict:
    """Is the argument valid: is the conclusion true whenever every premise is?

    Returns variables, valid, vacuous and countermodel. For an invalid argument
    the countermodel is the first assignment that makes every premise true and
    the conclusion false, as {"assignment", "premise_values", "conclusion_value"}.
    `vacuous` is True when the argument is valid only because no assignment
    makes all the premises true. With no premises, validity means the
    conclusion is a tautology.
    """
    check_premise_count(len(premises))
    names = _all_variables([*premises, conclusion])
    _check_size(names, [*premises, conclusion])

    premises_can_all_be_true = False
    for assignment in assignments(names):
        if not all(evaluate(premise, assignment) for premise in premises):
            continue
        premises_can_all_be_true = True
        conclusion_value = evaluate(conclusion, assignment)
        if not conclusion_value:
            return {
                "variables": names,
                "valid": False,
                "vacuous": False,
                "countermodel": {
                    "assignment": assignment,
                    "premise_values": [evaluate(premise, assignment) for premise in premises],
                    "conclusion_value": conclusion_value,
                },
            }
    return {
        "variables": names,
        "valid": True,
        "vacuous": not premises_can_all_be_true,
        "countermodel": None,
    }


def check_premise_count(count: int) -> None:
    """Raise LimitExceeded if an argument has more than MAX_PREMISES premises."""
    if count > MAX_PREMISES:
        raise LimitExceeded(
            f"{count} premises is too many (limit {MAX_PREMISES})", MAX_PREMISES, count
        )


def _all_variables(formulas: list[Formula]) -> list[str]:
    names: set[str] = set()
    for formula in formulas:
        names.update(variables(formula))
    return sorted(names)


def _check_size(names: list[str], formulas: list[Formula]) -> None:
    if len(names) > COMPUTE_LIMIT:
        raise LimitExceeded(
            f"{len(names)} variables is too many to compute (limit {COMPUTE_LIMIT})",
            COMPUTE_LIMIT,
            len(names),
        )
    work = 2 ** len(names) * sum(node_count(formula) for formula in formulas)
    if work > WORK_LIMIT:
        raise LimitExceeded(
            f"these formulas are too large to check together "
            f"(the limit is {WORK_LIMIT:,} steps; this would take {work:,})",
            WORK_LIMIT,
            work,
        )
