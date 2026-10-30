"""Pratt parser for propositional formulas.

Grammar (loosest to tightest binding):

    iff  := imp ('↔' imp)?          non-associative: a ↔ b ↔ c is an error
    imp  := or  ('→' imp)?          right-associative
    or   := and ('∨' and)*          left-associative
    and  := not ('∧' not)*          left-associative
    not  := '¬' not | atom
    atom := IDENT | '⊥' | '(' iff ')'

A Pratt parser reads this as a table of binding powers instead of one function
per level. expr(min_bp) parses an operand, then keeps absorbing operators whose
left binding power is at least min_bp. Passing right_bp = left_bp + 1 for the
recursive call makes an operator left-associative (an equal operator to the
right is not absorbed); right_bp = left_bp makes it right-associative.
"""

from .errors import (
    EMPTY_INPUT, NON_ASSOCIATIVE, TOO_DEEP, UNCLOSED_PAREN, UNEXPECTED_END,
    UNEXPECTED_TOKEN, UNMATCHED_PAREN, FormulaError,
)
from .lexer import tokenize
from .nodes import And, Bot, Formula, Iff, Imp, Not, Or, Var
from .tokens import Token, TokenKind

# Largest allowed nesting (parentheses, chained ¬, right-associative chains) and
# largest allowed tree height. Python's recursion limit is about 1000, and every
# later stage (printer, evaluator, rewriter) recurses over the tree, so the
# parser refuses anything taller instead of letting it crash later.
MAX_DEPTH = 100

# operator -> (left binding power, right binding power, node class)
_BINARY = {
    TokenKind.IFF: (10, 11, Iff),   # non-associative, enforced separately
    TokenKind.IMP: (20, 20, Imp),   # right-associative
    TokenKind.OR: (30, 31, Or),     # left-associative
    TokenKind.AND: (40, 41, And),   # left-associative
}
_NOT_BP = 50  # tighter than every binary operator


def parse(text: str) -> Formula:
    """Parse `text` into an AST, or raise FormulaError with a position."""
    return _Parser(tokenize(text)).parse()


def _describe(token: Token) -> str:
    return "the end of the input" if token.kind is TokenKind.EOF else repr(token.text)


def _too_deep(position: int) -> FormulaError:
    return FormulaError(TOO_DEEP, f"formula is nested too deeply (limit {MAX_DEPTH})", position)


def _check_height(height: int, position: int) -> None:
    if height > MAX_DEPTH:
        raise _too_deep(position)


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0
        self.depth = 0  # current recursion depth of expr()

    def peek(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> Token:
        token = self.tokens[self.i]
        if token.kind is not TokenKind.EOF:  # never step past EOF
            self.i += 1
        return token

    def parse(self) -> Formula:
        if self.peek().kind is TokenKind.EOF:
            raise FormulaError(EMPTY_INPUT, "enter a formula", self.peek().position)
        formula, _height = self.expr(0)
        extra = self.peek()
        if extra.kind is TokenKind.EOF:
            return formula
        if extra.kind is TokenKind.RPAREN:
            raise FormulaError(UNMATCHED_PAREN, "')' has no matching '('", extra.position)
        raise FormulaError(
            UNEXPECTED_TOKEN,
            f"expected an operator or the end of the formula, found {_describe(extra)}",
            extra.position,
        )

    def expr(self, min_bp: int) -> tuple[Formula, int]:
        """Parse an expression. Returns (tree, tree height)."""
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise _too_deep(self.peek().position)

        left, height = self.prefix()
        while True:
            op = self.peek()
            entry = _BINARY.get(op.kind)
            if entry is None:
                break
            left_bp, right_bp, node_class = entry
            if left_bp < min_bp:
                break

            self.advance()
            right, right_height = self.expr(right_bp)
            left = node_class(left, right)
            height = max(height, right_height) + 1
            _check_height(height, op.position)

            if node_class is Iff and self.peek().kind is TokenKind.IFF:
                raise FormulaError(
                    NON_ASSOCIATIVE,
                    "'↔' cannot be chained; add parentheses to show the grouping",
                    self.peek().position,
                )

        self.depth -= 1
        return left, height

    def prefix(self) -> tuple[Formula, int]:
        """Parse an operand: a variable, ⊥, a negation, or a parenthesised formula."""
        token = self.peek()
        kind = token.kind

        if kind is TokenKind.IDENT:
            self.advance()
            return Var(token.text), 1

        if kind is TokenKind.BOT:
            self.advance()
            return Bot(), 1

        if kind is TokenKind.NOT:
            self.advance()
            child, height = self.expr(_NOT_BP)
            _check_height(height + 1, token.position)
            return Not(child), height + 1

        if kind is TokenKind.LPAREN:
            self.advance()
            inner, height = self.expr(0)
            close = self.peek()
            if close.kind is TokenKind.RPAREN:
                self.advance()
                return inner, height
            if close.kind is TokenKind.EOF:
                raise FormulaError(
                    UNCLOSED_PAREN,
                    f"missing ')' for the '(' at position {token.position}",
                    close.position,
                )
            raise FormulaError(
                UNEXPECTED_TOKEN, f"expected ')', found {_describe(close)}", close.position
            )

        if kind is TokenKind.EOF:
            raise FormulaError(
                UNEXPECTED_END,
                "the formula ends too early; expected a variable, '⊥', '¬' or '('",
                token.position,
            )

        raise FormulaError(
            UNEXPECTED_TOKEN,
            f"unexpected {_describe(token)}; expected a variable, '⊥', '¬' or '('",
            token.position,
        )