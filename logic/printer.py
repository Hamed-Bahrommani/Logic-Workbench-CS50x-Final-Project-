"""Canonical printer: turns an AST back into text.

The printer is AST-preserving: it emits parentheses exactly where re-parsing the
output would otherwise build a different tree, and nowhere else. So
parse(to_string(tree)) == tree always holds, and And(And(P,Q),R) prints as
"P ∧ Q ∧ R" while And(P,And(Q,R)) prints as "P ∧ (Q ∧ R)".
"""

from .nodes import And, Bot, Formula, Iff, Imp, Not, Or, Var
from .tokens import CANONICAL, TokenKind

# Binding strength: higher binds tighter. Atoms (variables, ⊥) bind tightest.
_PRECEDENCE = {Iff: 1, Imp: 2, Or: 3, And: 4, Not: 5}
_ATOM = 6

# How an operator groups when the same operator is chained.
_ASSOCIATIVITY = {And: "left", Or: "left", Imp: "right", Iff: "none"}

_SYMBOL = {
    And: CANONICAL[TokenKind.AND],
    Or: CANONICAL[TokenKind.OR],
    Imp: CANONICAL[TokenKind.IMP],
    Iff: CANONICAL[TokenKind.IFF],
}


def to_string(formula: Formula) -> str:
    """Canonical text for `formula`: one spelling per operator, spaces around binary ones."""
    if isinstance(formula, Var):
        return formula.name
    if isinstance(formula, Bot):
        return CANONICAL[TokenKind.BOT]
    if isinstance(formula, Not):
        needs_parens = _precedence(formula.child) < _PRECEDENCE[Not]
        return CANONICAL[TokenKind.NOT] + _wrap(formula.child, needs_parens)

    node_class = type(formula)
    own = _PRECEDENCE[node_class]
    groups = _ASSOCIATIVITY[node_class]

    # A child of lower precedence always needs parentheses. A child with the same
    # precedence is the same operator, so it needs them unless the operator
    # naturally groups that way: left child for "left", right child for "right".
    left_parens = _precedence(formula.left) < own or (
        _precedence(formula.left) == own and groups != "left"
    )
    right_parens = _precedence(formula.right) < own or (
        _precedence(formula.right) == own and groups != "right"
    )
    return (
        f"{_wrap(formula.left, left_parens)} {_SYMBOL[node_class]} "
        f"{_wrap(formula.right, right_parens)}"
    )


def _precedence(formula: Formula) -> int:
    return _PRECEDENCE.get(type(formula), _ATOM)


def _wrap(formula: Formula, parenthesize: bool) -> str:
    text = to_string(formula)
    return f"({text})" if parenthesize else text