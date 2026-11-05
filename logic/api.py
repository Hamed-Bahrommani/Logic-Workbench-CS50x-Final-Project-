"""The engine's public functions, as the Flask app will call them.

Each takes the user's text and returns a plain, JSON-serialisable dict:

    {"ok": True, ...payload}              the operation ran
    {"ok": False, "error": {...}}         it could not run (bad syntax, too large)

`ok` means "the operation ran", never "the answer was yes": a contradiction or
an invalid argument is still ok=True. The UI explains results; the engine only
supplies the facts.

Operations that take several inputs report which one an error is in with
error["field"]: "left", "right", "premise-N" (counting from 1) or "conclusion".
"""
from collections.abc import Callable

from .checks import check_equivalence, check_premise_count, check_validity
from .errors import FormulaError, LimitExceeded
from .evaluate import variables
from .nodes import And, Bot, Formula, Iff, Imp, Not, Or, Var
from .parser import parse
from .printer import to_string
from .truth_table import build_truth_table
from logic.errors import LIMIT_EXCEEDED
from logic.rewrite import STRATEGIES, RewriteLimit, rewrite
from logic.proof import MAX_PROOF_LINES, check_lines, split_proof_text


def _run(operation: Callable[[], dict]) -> dict:
    """Call `operation`, turning the engine's exceptions into the error envelope."""
    try:
        return {"ok": True, **operation()}
    except (FormulaError, LimitExceeded) as err:
        return {"ok": False, "error": err.to_dict()}


def _parse_field(text: str, field: str) -> Formula:
    """Parse `text`; if it is malformed, record which input it came from."""
    try:
        return parse(text)
    except FormulaError as err:
        err.field = field
        raise


def _describe(formula: Formula) -> dict:
    """Both printings of a formula: minimal parentheses and explicit grouping."""
    return {"canonical": to_string(formula), "display": to_string(formula, explicit=True)}


def parse_formula(text: str) -> dict:
    """Parse `text`. Payload: ast, canonical, display, variables."""

    def operation() -> dict:
        formula = parse(text)
        return {
            "ast": _ast_to_dict(formula),
            "canonical": to_string(formula),
            "display": to_string(formula, explicit=True),
            "variables": variables(formula),
        }

    return _run(operation)


def truth_table(text: str) -> dict:
    """Truth table and classification of the formula in `text`."""

    def operation() -> dict:
        formula = parse(text)
        return {
            "canonical": to_string(formula),
            "display": to_string(formula, explicit=True),
            **build_truth_table(formula),
        }

    return _run(operation)


def equivalent(left: str, right: str) -> dict:
    """Are the formulas in `left` and `right` logically equivalent?

    Payload: left and right (each {canonical, display}), variables, equivalent,
    distinguishing (the first assignment where they differ, or None).
    """

    def operation() -> dict:
        first = _parse_field(left, "left")
        second = _parse_field(right, "right")
        return {
            "left": _describe(first),
            "right": _describe(second),
            **check_equivalence(first, second),
        }

    return _run(operation)


def valid(premises: list[str], conclusion: str) -> dict:
    """Is the argument with these premises and conclusion valid?

    Payload: premises (a list of {canonical, display}), conclusion, variables,
    valid, vacuous, countermodel (or None).
    """

    def operation() -> dict:
        check_premise_count(len(premises))   # before parsing, so a huge list is cheap to refuse
        parsed = [
            _parse_field(text, f"premise-{number}")
            for number, text in enumerate(premises, start=1)
        ]
        goal = _parse_field(conclusion, "conclusion")
        return {
            "premises": [_describe(premise) for premise in parsed],
            "conclusion": _describe(goal),
            **check_validity(parsed, goal),
        }

    return _run(operation)


def _display(formula) -> str:
    return to_string(formula, explicit=True)


def normal_form(text: str, strategy: str) -> dict:
    """Rewrite the formula in `text` to "nnf", "cnf" or "dnf", step by step.

    Payload: strategy, start and final (each {canonical, display}), steps (a list
    of {law, statement, before, after, whole}), already (True if no step was needed).
    """
    if strategy not in STRATEGIES:
        return {
            "ok": False,
            "error": {
                "code": "UNKNOWN_STRATEGY",
                "message": f"unknown strategy {strategy!r}; use one of: {', '.join(STRATEGIES)}",
            },
        }

    def operation() -> dict:
        formula = parse(text)
        outcome = rewrite(formula, strategy)
        return {
            "strategy": strategy,
            "start": _describe(formula),
            "steps": [
                {
                    "law": step.law.name,
                    "statement": step.law.statement,
                    "before": _display(step.before),
                    "after": _display(step.after),
                    "whole": _display(step.whole),
                }
                for step in outcome.steps
            ],
            "final": _describe(outcome.final),
            "already": not outcome.steps,
        }

    try:
        return _run(operation)
    except RewriteLimit as err:
        return {"ok": False, "error": {"code": LIMIT_EXCEEDED, "message": str(err)}}


def _request_error(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}


def check_proof(premises: list[str], conclusion: str, proof_text: str) -> dict:
    """Check a natural-deduction proof (Stage A: no subproofs).

    A bad premise or conclusion is an error for the whole request. A bad proof
    line is part of the result: see logic.proof.check_lines for the payload,
    plus premises and conclusion ({canonical, display}).
    """
    entries = split_proof_text(proof_text)
    if not entries:
        return _request_error("EMPTY_PROOF", "write at least one proof line")
    if len(entries) > MAX_PROOF_LINES:
        return _request_error(
            LIMIT_EXCEEDED,
            f"the proof has {len(entries)} lines; the limit is {MAX_PROOF_LINES}",
        )

    def operation() -> dict:
        check_premise_count(len(premises))
        parsed = [
            _parse_field(text, f"premise-{number}")
            for number, text in enumerate(premises, start=1)
        ]
        goal = _parse_field(conclusion, "conclusion")
        return {
            "premises": [_describe(p) for p in parsed],
            "conclusion": _describe(goal),
            **check_lines(parsed, goal, entries),
        }

    return _run(operation)

_NODE_NAMES = {Not: "not", And: "and", Or: "or", Imp: "imp", Iff: "iff"}


def _ast_to_dict(formula: Formula) -> dict:
    if isinstance(formula, Var):
        return {"type": "var", "name": formula.name}
    if isinstance(formula, Bot):
        return {"type": "bot"}
    if isinstance(formula, Not):
        return {"type": "not", "child": _ast_to_dict(formula.child)}
    return {
        "type": _NODE_NAMES[type(formula)],
        "left": _ast_to_dict(formula.left),
        "right": _ast_to_dict(formula.right),
    }
