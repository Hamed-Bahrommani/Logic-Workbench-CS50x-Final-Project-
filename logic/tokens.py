"""Token definitions shared by the lexer, the parser and the printer."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    IDENT = auto()
    NOT = auto()
    AND = auto()
    OR = auto()
    IMP = auto()
    IFF = auto()
    BOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    EOF = auto()


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    position: int  # 0-based index of the token's first character


# Every spelling the lexer accepts. Today no spelling is a prefix of another
# ("<", "<-", "-" and "_" are not tokens), but the lexer still tries the longest
# first so that adding an alias later cannot silently change how input lexes.
SYMBOLS = {
    "¬": TokenKind.NOT, "~": TokenKind.NOT, "!": TokenKind.NOT,
    "∧": TokenKind.AND, "&": TokenKind.AND,
    "∨": TokenKind.OR, "|": TokenKind.OR,
    "→": TokenKind.IMP, "->": TokenKind.IMP,
    "↔": TokenKind.IFF, "<->": TokenKind.IFF,
    "⊥": TokenKind.BOT, "_|_": TokenKind.BOT,
    "(": TokenKind.LPAREN, ")": TokenKind.RPAREN,
}

# The single spelling the printer emits for each operator.
CANONICAL = {
    TokenKind.NOT: "¬",
    TokenKind.AND: "∧",
    TokenKind.OR: "∨",
    TokenKind.IMP: "→",
    TokenKind.IFF: "↔",
    TokenKind.BOT: "⊥",
}

# T and F label truth-table cells, so they cannot be variable names.
RESERVED_NAMES = frozenset({"T", "F"})