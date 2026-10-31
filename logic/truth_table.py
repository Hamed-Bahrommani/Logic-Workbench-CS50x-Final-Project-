"""Truth tables and classification (tautology / contradiction / contingency)."""

from .errors import LimitExceeded
from .evaluate import assignments, evaluate, variables
from .nodes import Formula

# With n variables a table has 2**n rows. Rows are only returned for display up
# to DISPLAY_LIMIT variables (256 rows); the answer is still computed up to
# COMPUTE_LIMIT variables (65,536 rows) and refused beyond that.
DISPLAY_LIMIT = 8
COMPUTE_LIMIT = 16


def classify(true_count: int, row_count: int) -> str:
    """Name a formula from how many of its rows are true."""
    if true_count == row_count:
        return "tautology"
    if true_count == 0:
        return "contradiction"
    return "contingency"


def build_truth_table(formula: Formula) -> dict:
    """Evaluate `formula` on every assignment.

    Returns a dict with: variables, row_count, true_count, classification,
    satisfiable, rows_omitted and (unless omitted) rows, a list of
    {"assignment": {...}, "value": bool} in textbook order.

    Raises LimitExceeded if the formula has more than COMPUTE_LIMIT variables.
    """
    names = variables(formula)
    if len(names) > COMPUTE_LIMIT:
        raise LimitExceeded(
            f"{len(names)} variables is too many to compute (limit {COMPUTE_LIMIT})",
            COMPUTE_LIMIT,
            len(names),
        )

    keep_rows = len(names) <= DISPLAY_LIMIT
    rows = []
    row_count = 0
    true_count = 0
    for assignment in assignments(names):
        value = evaluate(formula, assignment)
        row_count += 1
        true_count += value
        if keep_rows:
            rows.append({"assignment": assignment, "value": value})

    table = {
        "variables": names,
        "row_count": row_count,
        "true_count": true_count,
        "classification": classify(true_count, row_count),
        "satisfiable": true_count > 0,
        "rows_omitted": not keep_rows,
    }
    if keep_rows:
        table["rows"] = rows
    return table