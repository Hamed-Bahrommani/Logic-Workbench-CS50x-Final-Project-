"""The one error type raised by the lexer and the parser."""

# Error codes. Tests pin these, so a typo here fails loudly.
UNEXPECTED_CHAR = "UNEXPECTED_CHAR"      # a character that is not part of the language
RESERVED_NAME = "RESERVED_NAME"          # the variable names T and F
EMPTY_INPUT = "EMPTY_INPUT"              # nothing but whitespace
UNEXPECTED_TOKEN = "UNEXPECTED_TOKEN"    # a valid token in the wrong place
UNEXPECTED_END = "UNEXPECTED_END"        # the formula stops while an operand is still needed
UNCLOSED_PAREN = "UNCLOSED_PAREN"        # '(' without a matching ')'
UNMATCHED_PAREN = "UNMATCHED_PAREN"      # ')' without a matching '('
NON_ASSOCIATIVE = "NON_ASSOCIATIVE"      # a <-> b <-> c needs parentheses
TOO_DEEP = "TOO_DEEP"                    # nesting beyond the parser's depth limit


class FormulaError(Exception):
    """A syntax problem, with the 0-based index of the offending character.

    For problems at the end of the input the position is len(text).
    """

    def __init__(self, code: str, message: str, position: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.position = position

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "position": self.position}