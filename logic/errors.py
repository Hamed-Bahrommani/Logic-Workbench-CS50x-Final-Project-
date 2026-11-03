"""The error types raised inside the engine."""

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
LIMIT_EXCEEDED = "LIMIT_EXCEEDED"        # too many variables to compute


class FormulaError(Exception):
    """A syntax problem, with the 0-based index of the offending character.

    For problems at the end of the input the position is len(text).
    `field` names which input the problem is in when an operation takes
    several (for example "left" or "premise-2"); it is None otherwise.
    """

    def __init__(self, code: str, message: str, position: int, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.position = position
        self.field = field

    def to_dict(self) -> dict:
        error = {"code": self.code, "message": self.message, "position": self.position}
        if self.field is not None:
            error["field"] = self.field
        return error

class LimitExceeded(Exception):
    """The input is valid but too large to compute (too many variables)."""

    def __init__(self, message: str, limit: int, actual: int):
        super().__init__(message)
        self.code = LIMIT_EXCEEDED
        self.message = message
        self.limit = limit
        self.actual = actual

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "limit": self.limit,
            "actual": self.actual,
        }