import re

import pytest

from app import ARGUMENT_EXAMPLES, EQUIVALENCE_EXAMPLES, MAX_INPUT_LENGTH, app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def get(client, path, **params):
    """GET a page with query-string parameters. Returns (status, html)."""
    response = client.get(path, query_string=params or None)
    return response.status_code, response.get_data(as_text=True)


def table_row_count(html):
    return len(re.findall(r"<tr>", html))


def cell_letters(html):
    """Every T/F cell, in document order."""
    return re.findall(r'<td class="[^"]*">([TF])</td>', html)


def squash(html):
    return re.sub(r"\s+", " ", html)


# ======================================================================
# /equivalence
# ======================================================================

def test_equivalence_empty_page(client):
    status, html = get(client, "/equivalence")
    assert status == 200
    assert 'name="left"' in html
    assert 'name="right"' in html
    assert "Try an example" in html
    assert "<table" not in html
    assert "can't be computed" not in html


@pytest.mark.parametrize(
    "example",
    [pytest.param(e, id=f"example-{n}") for n, e in enumerate(EQUIVALENCE_EXAMPLES)],
)
def test_equivalence_examples_work(client, example):
    status, html = get(client, "/equivalence", left=example["left"], right=example["right"])
    assert status == 200
    assert "Result" in html
    assert "can't be computed" not in html


def test_equivalent_formulas(client):
    status, html = get(client, "/equivalence", left="P → Q", right="¬P ∨ Q")
    assert status == 200
    assert '<span class="badge good">Equivalent</span>' in html
    assert "Not equivalent" not in html
    assert "<table" not in html


def test_non_equivalent_formulas_show_the_distinguishing_row(client):
    _, html = get(client, "/equivalence", left="P → Q", right="Q → P")
    assert '<span class="badge bad">Not equivalent</span>' in html
    assert table_row_count(html) == 2                    # header + one row
    # first difference in truth-table order is P=T, Q=F; left is F, right is T
    assert cell_letters(html) == ["T", "F", "F", "T"]


def test_different_variable_sets_use_the_union(client):
    _, html = get(client, "/equivalence", left="P", right="Q")
    assert '<th scope="col">P</th>' in html
    assert '<th scope="col">Q</th>' in html
    # P=T, Q=F is the first row that differs; left is T, right is F
    assert cell_letters(html) == ["T", "F", "T", "F"]


def test_equivalent_despite_an_extra_variable(client):
    _, html = get(client, "/equivalence", left="P", right="P ∧ (Q ∨ ¬Q)")
    assert '<span class="badge good">Equivalent</span>' in html


def test_equivalence_shows_explicit_grouping(client):
    _, html = get(client, "/equivalence", left="P → (Q ∧ ¬R)", right="P")
    assert "First: <code>P → (Q ∧ ¬R)</code>" in html


def test_equivalence_keeps_both_inputs(client):
    _, html = get(client, "/equivalence", left="P -> Q", right="Q -> P")
    assert 'value="P -&gt; Q"' in html
    assert 'value="Q -&gt; P"' in html


def test_equivalence_error_in_the_first_formula(client):
    status, html = get(client, "/equivalence", left="P ∧", right="Q")
    assert status == 200
    assert "That formula can't be computed" in html
    assert "Problem in: <strong>First formula</strong>" in html
    assert '<span class="line">P ∧</span>' in html
    assert '<span class="caret">   ^</span>' in html
    assert "<table" not in html


def test_equivalence_error_in_the_second_formula(client):
    _, html = get(client, "/equivalence", left="P", right="Q @ R")
    assert "Problem in: <strong>Second formula</strong>" in html
    assert '<span class="line">Q @ R</span>' in html
    assert '<span class="caret">  ^</span>' in html


def test_equivalence_with_only_one_side_is_an_error(client):
    _, html = get(client, "/equivalence", left="P")
    assert "EMPTY_INPUT" in html
    assert "Problem in: <strong>Second formula</strong>" in html


@pytest.mark.parametrize("field, label", [
    pytest.param("left", "First formula", id="left"),
    pytest.param("right", "Second formula", id="right"),
])
def test_equivalence_input_too_long(client, field, label):
    params = {"left": "P", "right": "P"}
    params[field] = "P" * (MAX_INPUT_LENGTH + 1)
    status, html = get(client, "/equivalence", **params)
    assert status == 200
    assert "INPUT_TOO_LONG" in html
    assert f"Problem in: <strong>{label}</strong>" in html
    assert "caret" not in html


def test_equivalence_limit_error(client):
    left = " ∧ ".join(f"v{i}" for i in range(17))
    status, html = get(client, "/equivalence", left=left, right="P")
    assert status == 200
    assert "LIMIT_EXCEEDED" in html
    assert "caret" not in html


def test_equivalence_escapes_hostile_input(client):
    _, html = get(client, "/equivalence", left="<script>alert(1)</script>", right='"><img src=x>')
    assert "<script>alert" not in html
    assert "<img" not in html


# ======================================================================
# /argument
# ======================================================================

def test_argument_empty_page(client):
    status, html = get(client, "/argument")
    assert status == 200
    assert 'name="premises"' in html
    assert 'name="conclusion"' in html
    assert "Try an example" in html
    assert "<table" not in html
    assert "can't be computed" not in html


@pytest.mark.parametrize(
    "example",
    [pytest.param(e, id=f"example-{n}") for n, e in enumerate(ARGUMENT_EXAMPLES)],
)
def test_argument_examples_work(client, example):
    status, html = get(
        client, "/argument", premises=example["premises"], conclusion=example["conclusion"]
    )
    assert status == 200
    assert "Result" in html
    assert "can't be computed" not in html


def test_valid_argument(client):
    _, html = get(client, "/argument", premises="P → Q\nP", conclusion="Q")
    assert '<span class="badge good">Valid</span>' in html
    assert '<ol class="premise-list">' in html
    assert "<table" not in html
    assert "contradict each other" not in squash(html)


def test_invalid_argument_shows_a_countermodel(client):
    _, html = get(client, "/argument", premises="P → Q\nQ", conclusion="P")
    assert '<span class="badge bad">Invalid</span>' in html
    assert table_row_count(html) == 2
    # P=F, Q=T; premises P → Q and Q are both T; conclusion P is F
    assert cell_letters(html) == ["F", "T", "T", "T", "F"]


def test_vacuous_validity_is_flagged(client):
    _, html = get(client, "/argument", premises="P ∧ ¬P", conclusion="Q")
    assert '<span class="badge good">Valid</span>' in html
    assert "contradict each other" in squash(html)


def test_no_premises_valid_conclusion(client):
    _, html = get(client, "/argument", premises="", conclusion="P ∨ ¬P")
    assert "No premises." in html
    assert '<span class="badge good">Valid</span>' in html
    assert "contradict each other" not in squash(html)


def test_no_premises_invalid_conclusion(client):
    _, html = get(client, "/argument", premises="", conclusion="P")
    assert "No premises." in html
    assert '<span class="badge bad">Invalid</span>' in html
    assert cell_letters(html) == ["F", "F"]


def test_blank_lines_do_not_shift_premise_numbers(client):
    _, html = get(client, "/argument", premises="P\n\n\nQ ∧", conclusion="R")
    assert "Problem in: <strong>Premise 2</strong>" in html


def test_error_in_a_premise_shows_its_own_line_and_caret(client):
    _, html = get(client, "/argument", premises="P\nP @ Q", conclusion="R")
    assert "Problem in: <strong>Premise 2</strong>" in html
    assert '<span class="line">P @ Q</span>' in html
    assert '<span class="caret">  ^</span>' in html


def test_error_in_the_conclusion(client):
    _, html = get(client, "/argument", premises="P", conclusion="Q ∧")
    assert "Problem in: <strong>Conclusion</strong>" in html
    assert '<span class="caret">   ^</span>' in html


def test_empty_conclusion_is_an_error(client):
    _, html = get(client, "/argument", premises="P", conclusion="")
    assert "EMPTY_INPUT" in html
    assert "Problem in: <strong>Conclusion</strong>" in html


def test_too_many_premises(client):
    _, html = get(client, "/argument", premises="\n".join(["P"] * 21), conclusion="P")
    assert "LIMIT_EXCEEDED" in html
    assert "<table" not in html


def test_exactly_the_maximum_number_of_premises_is_accepted(client):
    _, html = get(client, "/argument", premises="\n".join(["P"] * 20), conclusion="P")
    assert '<span class="badge good">Valid</span>' in html


def test_premise_too_long(client):
    _, html = get(client, "/argument", premises="P" * (MAX_INPUT_LENGTH + 1), conclusion="P")
    assert "INPUT_TOO_LONG" in html
    assert "Problem in: <strong>Premise 1</strong>" in html
    assert "caret" not in html


def test_whole_premise_list_too_long(client):
    _, html = get(client, "/argument", premises="P\n" * 10001, conclusion="P")
    assert "INPUT_TOO_LONG" in html
    assert "list of premises" in html


def test_conclusion_too_long(client):
    _, html = get(client, "/argument", premises="P", conclusion="P" * (MAX_INPUT_LENGTH + 1))
    assert "INPUT_TOO_LONG" in html
    assert "Problem in: <strong>Conclusion</strong>" in html


def test_premises_stay_in_the_textarea(client):
    _, html = get(client, "/argument", premises="P → Q\nP", conclusion="Q")
    assert "P → Q\nP</textarea>" in html
    assert 'value="Q"' in html


def test_argument_escapes_hostile_input(client):
    _, html = get(
        client, "/argument", premises="<script>alert(1)</script>", conclusion="<img src=x>"
    )
    assert "<script>alert" not in html
    assert "<img" not in html


# ======================================================================
# navigation, palette, routing, JavaScript
# ======================================================================

PAGES = [
    pytest.param("/", id="truth-table"),
    pytest.param("/equivalence", id="equivalence"),
    pytest.param("/argument", id="argument"),
]


@pytest.mark.parametrize("path", PAGES)
def test_nav_marks_exactly_the_current_page(client, path):
    _, html = get(client, path)
    assert html.count('aria-current="page"') == 1
    assert re.search(rf'<a href="{path}"[^>]*aria-current="page"', html)
    for other in ("/", "/equivalence", "/argument"):
        assert f'<a href="{other}"' in html


@pytest.mark.parametrize("path", PAGES)
def test_every_page_has_the_hidden_symbol_palette(client, path):
    _, html = get(client, path)
    assert re.search(r'<div id="symbols"[^>]*\bhidden\b', html)
    for symbol in "¬∧∨→↔⊥":
        assert f'data-insert="{symbol}"' in html


@pytest.mark.parametrize("path, expected", [
    pytest.param("/", 1, id="truth-table"),
    pytest.param("/equivalence", 2, id="equivalence"),
    pytest.param("/argument", 2, id="argument"),
])
def test_formula_inputs_are_marked_for_the_palette(client, path, expected):
    _, html = get(client, path)
    assert len(re.findall(r'class="formula-input"', html)) == expected


@pytest.mark.parametrize("path", ["/equivalence", "/argument"])
def test_new_pages_reject_post(client, path):
    assert client.post(path, data={"left": "P"}).status_code == 405


def test_javascript_targets_the_focused_formula_input(client):
    response = client.get("/static/app.js")
    source = response.get_data(as_text=True)
    response.close()
    assert ".formula-input" in source
    assert "focus" in source
