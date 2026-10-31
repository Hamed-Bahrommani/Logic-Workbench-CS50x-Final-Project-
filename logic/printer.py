"""Canonical printer: turns an AST back into text.

Two modes, both AST-preserving (parse(to_string(tree)) == tree always holds):

* minimal (the default): parentheses exactly where re-parsing the output would
  otherwise build a different tree, and nowhere else. And(And(P,Q),R) prints as
  "P ∧ Q ∧ R"; And(P,And(Q,R)) prints as "P ∧ (Q ∧ R)".
* explicit (explicit=True): the same, plus parentheses around every binary
  sub-formula that sits under a different binary operator, so the grouping
  never depends on remembering precedence. Or(P, And(Q,R)) prints as
  "P ∨ (Q ∧ R)". The web page uses this mode.
"""

from .nodes import And, Bot, Formula, Iff, Imp, Not, Or, Var
from .tokens import CANONICAL, TokenKind

# Binding strength: higher binds tighter. Atoms (variables, ⊥) bind tightest.
# Every binary operator has its own level, so equal precedence means the same operator.
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


def to_string(formula: Formula, explicit: bool = False) -> str:
    """Text for `formula`: one spelling per operator, spaces around binary ones."""
    if isinstance(formula, Var):
        return formula.name
    if isinstance(formula, Bot):
        return CANONICAL[TokenKind.BOT]
    if isinstance(formula, Not):
        needs_parens = _precedence(formula.child) < _PRECEDENCE[Not]
        return CANONICAL[TokenKind.NOT] + _wrap(formula.child, needs_parens, explicit)

    node_class = type(formula)
    left_parens = _child_needs_parens(formula.left, node_class, "left", explicit)
    right_parens = _child_needs_parens(formula.right, node_class, "right", explicit)
    return (
        f"{_wrap(formula.left, left_parens, explicit)} {_SYMBOL[node_class]} "
        f"{_wrap(formula.right, right_parens, explicit)}"
    )


def _child_needs_parens(child: Formula, parent_class: type, side: str, explicit: bool) -> bool:
    """Whether `child`, on the given side of a `parent_class` node, is wrapped in parentheses."""
    child_class = type(child)
    if child_class not in _SYMBOL:
        return False  # a variable, ⊥ or ¬ binds tighter than any binary operator

    parent_precedence = _PRECEDENCE[parent_class]
    child_precedence = _PRECEDENCE[child_class]
    if child_precedence < parent_precedence:
        return True   # loosely-binding child: parentheses are required
    if child_precedence == parent_precedence:
        # The same operator chained: parentheses are required unless the
        # operator naturally groups that way (left child for "left", right
        # child for "right").
        return _ASSOCIATIVITY[parent_class] != side
    return explicit   # tighter-binding binary child: parentheses only for clarity


def _precedence(formula: Formula) -> int:
    return _PRECEDENCE.get(type(formula), _ATOM)


def _wrap(formula: Formula, parenthesize: bool, explicit: bool) -> str:
    text = to_string(formula, explicit)
    return f"({text})" if parenthesize else text