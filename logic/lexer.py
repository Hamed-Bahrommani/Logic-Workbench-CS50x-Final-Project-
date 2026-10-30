"""Lexer: turns formula text into a list of tokens, each with its position."""

import string

from .errors import RESERVED_NAME, UNEXPECTED_CHAR, FormulaError
from .tokens import RESERVED_NAMES, SYMBOLS, Token, TokenKind

_WHITESPACE = " \t\r\n"
_IDENT_START = string.ascii_letters
_IDENT_REST = string.ascii_letters + string.digits + "_"

# Longest spellings first. No alias is a prefix of another today, so the order
# changes no result; it keeps that true if a prefixing alias is ever added.
_SYMBOLS_LONGEST_FIRST = sorted(SYMBOLS, key=len, reverse=True)


def tokenize(text: str) -> list[Token]:
    """Split `text` into tokens, ending with an EOF token at position len(text).

    The input is never stripped, so every position is an index into `text`.
    """
    tokens: list[Token] = []
    i = 0
    while i < len(text):
        ch = text[i]

        if ch in _WHITESPACE:
            i += 1
            continue

        symbol = next((s for s in _SYMBOLS_LONGEST_FIRST if text.startswith(s, i)), None)
        if symbol is not None:
            tokens.append(Token(SYMBOLS[symbol], symbol, i))
            i += len(symbol)
        elif ch in _IDENT_START:
            j = i + 1
            while j < len(text) and text[j] in _IDENT_REST:
                j += 1
            name = text[i:j]
            if name in RESERVED_NAMES:
                raise FormulaError(
                    RESERVED_NAME,
                    f"{name!r} is reserved for truth tables; choose another variable name",
                    i,
                )
            tokens.append(Token(TokenKind.IDENT, name, i))
            i = j
        else:
            raise FormulaError(UNEXPECTED_CHAR, f"unexpected character {ch!r}", i)

    tokens.append(Token(TokenKind.EOF, "", len(text)))
    return tokens