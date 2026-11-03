"""AST node classes.

Named nodes.py, not ast.py, so it can never shadow Python's standard-library
`ast` module. The nodes are frozen dataclasses, so == is structural equality:
And(And(P, Q), R) != And(P, And(Q, R)), exactly as the spec requires.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Var:
    name: str


@dataclass(frozen=True, slots=True)
class Bot:
    """The constant false, written ⊥."""


@dataclass(frozen=True, slots=True)
class Not:
    child: "Formula"


@dataclass(frozen=True, slots=True)
class And:
    left: "Formula"
    right: "Formula"


@dataclass(frozen=True, slots=True)
class Or:
    left: "Formula"
    right: "Formula"


@dataclass(frozen=True, slots=True)
class Imp:
    left: "Formula"
    right: "Formula"


@dataclass(frozen=True, slots=True)
class Iff:
    left: "Formula"
    right: "Formula"


Formula = Var | Bot | Not | And | Or | Imp | Iff


def node_count(formula: Formula) -> int:
    """The number of nodes in the tree: each variable, ⊥ and connective counts as one."""
    if isinstance(formula, (Var, Bot)):
        return 1
    if isinstance(formula, Not):
        return 1 + node_count(formula.child)
    return 1 + node_count(formula.left) + node_count(formula.right)
