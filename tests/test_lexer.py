
import pytest

from logic.errors import RESERVED_NAME, UNEXPECTED_CHAR, FormulaError
from logic.lexer import tokenize
from logic.tokens import TokenKind as K


def kinds(text):
    return [t.kind for t in tokenize(text)]


@pytest.mark.parametrize("text, expected", [
    ("", [K.EOF]),
    ("P", [K.IDENT, K.EOF]),
    ("⊥", [K.BOT, K.EOF]),
    ("_|_", [K.BOT, K.EOF]),
    ("(P)", [K.LPAREN, K.IDENT, K.RPAREN, K.EOF]),
    ("¬P ∧ Q", [K.NOT, K.IDENT, K.AND, K.IDENT, K.EOF]),
    ("~P & Q | R", [K.NOT, K.IDENT, K.AND, K.IDENT, K.OR, K.IDENT, K.EOF]),
    ("!P", [K.NOT, K.IDENT, K.EOF]),
    ("P -> Q", [K.IDENT, K.IMP, K.IDENT, K.EOF]),
    ("P <-> Q", [K.IDENT, K.IFF, K.IDENT, K.EOF]),
    ("P → Q ↔ R", [K.IDENT, K.IMP, K.IDENT, K.IFF, K.IDENT, K.EOF]),
])
def test_token_kinds(text, expected):
    assert kinds(text) == expected


def test_multi_character_operators_are_single_tokens():
    # "<->" must be one IFF token, and the "->" inside it must not be an IMP.
    assert kinds("P<->Q->R") == [K.IDENT, K.IFF, K.IDENT, K.IMP, K.IDENT, K.EOF]
    # "_|_" is one BOT token, not "_" "|" "_".
    assert kinds("P&_|_") == [K.IDENT, K.AND, K.BOT, K.EOF]


def test_text_and_positions():
    tokens = tokenize("  rain  -> Q1")
    assert [(t.text, t.position) for t in tokens] == [
        ("rain", 2), ("->", 8), ("Q1", 11), ("", 13),
    ]


def test_eof_position_is_len_of_untrimmed_input():
    assert tokenize("   ")[-1].position == 3
    assert tokenize("P ")[-1].position == 2


@pytest.mark.parametrize("name", ["P", "PQ", "rain", "Q1", "x_1", "True", "T1", "Fx", "TF"])
def test_identifiers_are_single_tokens(name):
    tokens = tokenize(name)
    assert [t.kind for t in tokens] == [K.IDENT, K.EOF]
    assert tokens[0].text == name


@pytest.mark.parametrize("text, position", [("T", 0), ("F", 0), ("P ∧ T", 4), ("F → P", 0)])
def test_reserved_names_rejected(text, position):
    with pytest.raises(FormulaError) as err:
        tokenize(text)
    assert err.value.code == RESERVED_NAME
    assert err.value.position == position


@pytest.mark.parametrize("text, position", [
    ("P @ Q", 2),
    ("P - Q", 2),      # a lone '-' is not '->'
    ("P < Q", 2),
    ("P <- Q", 2),     # '<-' is not '<->'
    ("P => Q", 2),
    ("1P", 0),         # identifiers cannot start with a digit
    ("_P", 0),         # ... or an underscore
    ("$", 0),
    ("P ∧ Q.", 5),
    ("é", 0),          # ASCII letters only
    ("Pé", 1),
])
def test_unexpected_characters(text, position):
    with pytest.raises(FormulaError) as err:
        tokenize(text)
    assert err.value.code == UNEXPECTED_CHAR
    assert err.value.position == position