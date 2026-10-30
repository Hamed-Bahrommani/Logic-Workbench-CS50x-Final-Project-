
import pytest

from logic.errors import (
    EMPTY_INPUT, NON_ASSOCIATIVE, RESERVED_NAME, TOO_DEEP, UNCLOSED_PAREN,
    UNEXPECTED_CHAR, UNEXPECTED_END, UNEXPECTED_TOKEN, UNMATCHED_PAREN,
    FormulaError,
)
from logic.nodes import And, Bot, Iff, Imp, Not, Or, Var
from logic.parser import MAX_DEPTH, parse

P, Q, R, S = Var("P"), Var("Q"), Var("R"), Var("S")

AST_CASES = [
    # atoms and negation
    ("P", P),
    ("⊥", Bot()),
    ("¬P", Not(P)),
    ("¬¬P", Not(Not(P))),
    ("¬⊥", Not(Bot())),
    ("¬(P ∧ Q)", Not(And(P, Q))),
    # precedence: ¬ > ∧ > ∨ > → > ↔
    ("¬P ∧ Q", And(Not(P), Q)),
    ("P ∨ Q ∧ R", Or(P, And(Q, R))),
    ("P ∧ Q ∨ R", Or(And(P, Q), R)),
    ("P → Q ∨ R", Imp(P, Or(Q, R))),
    ("P ∨ Q → R", Imp(Or(P, Q), R)),
    ("P ↔ Q → R", Iff(P, Imp(Q, R))),
    ("P → Q ↔ R", Iff(Imp(P, Q), R)),
    ("¬P → Q", Imp(Not(P), Q)),
    ("P → ¬Q", Imp(P, Not(Q))),
    ("P ∧ Q → R ∨ ¬S", Imp(And(P, Q), Or(R, Not(S)))),
    ("¬(P ∨ Q) ↔ ¬P ∧ ¬Q", Iff(Not(Or(P, Q)), And(Not(P), Not(Q)))),
    # associativity: ∧ and ∨ left, → right, ↔ needs parentheses
    ("P ∧ Q ∧ R", And(And(P, Q), R)),
    ("P ∧ (Q ∧ R)", And(P, And(Q, R))),
    ("P ∨ Q ∨ R", Or(Or(P, Q), R)),
    ("P ∨ (Q ∨ R)", Or(P, Or(Q, R))),
    ("P → Q → R", Imp(P, Imp(Q, R))),
    ("(P → Q) → R", Imp(Imp(P, Q), R)),
    ("(P ↔ Q) ↔ R", Iff(Iff(P, Q), R)),
    ("P ↔ (Q ↔ R)", Iff(P, Iff(Q, R))),
    # redundant parentheses and whitespace
    ("(P)", P),
    ("((P ∧ Q))", And(P, Q)),
    ("  P  ∧\tQ  ", And(P, Q)),
    ("P ∧ Q\n", And(P, Q)),
    # identifiers
    ("PQ", Var("PQ")),   # one variable, not P ∧ Q
    ("p", Var("p")),     # case-sensitive
    ("Q1_x", Var("Q1_x")),
]


@pytest.mark.parametrize("text, expected", AST_CASES)
def test_parse_builds_expected_ast(text, expected):
    assert parse(text) == expected


def test_variables_are_case_sensitive():
    assert parse("p") != parse("P")


def test_associativity_gives_different_asts():
    assert parse("P ∧ Q ∧ R") != parse("P ∧ (Q ∧ R)")
    assert parse("P → Q → R") != parse("(P → Q) → R")


@pytest.mark.parametrize("ascii_text, unicode_text", [
    ("~P & Q", "¬P ∧ Q"),
    ("!P | Q", "¬P ∨ Q"),
    ("P -> Q", "P → Q"),
    ("P <-> Q", "P ↔ Q"),
    ("_|_", "⊥"),
    ("~~P", "¬¬P"),
    ("P&Q|R->S<->~_|_", "P∧Q∨R→S↔¬⊥"),
])
def test_ascii_aliases_match_unicode(ascii_text, unicode_text):
    assert parse(ascii_text) == parse(unicode_text)


ERROR_CASES = [
    ("", EMPTY_INPUT, 0),
    ("   ", EMPTY_INPUT, 3),
    ("P @ Q", UNEXPECTED_CHAR, 2),
    ("P - Q", UNEXPECTED_CHAR, 2),
    ("1P", UNEXPECTED_CHAR, 0),
    ("T", RESERVED_NAME, 0),
    ("F", RESERVED_NAME, 0),
    ("P ∧ F", RESERVED_NAME, 4),
    ("P ∧", UNEXPECTED_END, 3),
    ("P → ", UNEXPECTED_END, 4),       # trailing space counts: nothing is stripped
    ("P ∧ Q ∨", UNEXPECTED_END, 7),
    ("¬", UNEXPECTED_END, 1),
    ("¬ ¬", UNEXPECTED_END, 3),
    ("P ∧ Q)", UNMATCHED_PAREN, 5),
    ("(P ∧ Q", UNCLOSED_PAREN, 6),
    ("P ∧ (Q", UNCLOSED_PAREN, 6),
    ("(P Q)", UNEXPECTED_TOKEN, 3),
    ("P Q", UNEXPECTED_TOKEN, 2),
    ("P ∧ ∧ Q", UNEXPECTED_TOKEN, 4),
    ("P ↔ ↔ Q", UNEXPECTED_TOKEN, 4),
    ("()", UNEXPECTED_TOKEN, 1),
    (")", UNEXPECTED_TOKEN, 0),
    ("∧ P", UNEXPECTED_TOKEN, 0),
    ("P ↔ Q ↔ R", NON_ASSOCIATIVE, 6),
    ("P ↔ Q ∧ R ↔ S", NON_ASSOCIATIVE, 10),
    ("P → Q ↔ R ↔ S", NON_ASSOCIATIVE, 10),
    ("(P ↔ Q ↔ R)", NON_ASSOCIATIVE, 7),
]


@pytest.mark.parametrize("text, code, position", ERROR_CASES)
def test_syntax_errors_have_code_and_position(text, code, position):
    with pytest.raises(FormulaError) as err:
        parse(text)
    assert err.value.code == code
    assert err.value.position == position
    assert err.value.position <= len(text)


def test_error_to_dict():
    with pytest.raises(FormulaError) as err:
        parse("P ∧")
    d = err.value.to_dict()
    assert d["code"] == UNEXPECTED_END
    assert d["position"] == 3
    assert isinstance(d["message"], str) and d["message"]


# --- depth limit: pathological input must give TOO_DEEP, never RecursionError ---

@pytest.mark.parametrize("text", [
    pytest.param("¬" * 5000 + "P", id="negation-chain"),
    pytest.param("(" * 5000 + "P" + ")" * 5000, id="nested-parentheses"),
    pytest.param("∧".join(["P"] * 5000), id="long-left-assoc-chain"),
    pytest.param("→".join(["P"] * 5000), id="long-right-assoc-chain"),
])
def test_pathological_depth_is_a_clean_error(text):
    with pytest.raises(FormulaError) as err:
        parse(text)
    assert err.value.code == TOO_DEEP
    assert 0 <= err.value.position <= len(text)


def test_depth_error_position_for_nesting():
    with pytest.raises(FormulaError) as err:
        parse("¬" * 5000 + "P")
    assert err.value.position == MAX_DEPTH
    with pytest.raises(FormulaError) as err:
        parse("(" * 5000 + "P" + ")" * 5000)
    assert err.value.position == MAX_DEPTH


def test_depth_boundaries():
    parse("¬" * (MAX_DEPTH - 1) + "P")                  # accepted
    parse("∧".join(["P"] * MAX_DEPTH))                  # tree height == MAX_DEPTH: accepted
    with pytest.raises(FormulaError):
        parse("¬" * MAX_DEPTH + "P")
    with pytest.raises(FormulaError):
        parse("∧".join(["P"] * (MAX_DEPTH + 1)))

