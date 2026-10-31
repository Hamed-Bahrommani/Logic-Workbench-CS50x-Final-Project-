import re

import pytest
from flask import render_template

from app import CLASSIFICATION_HELP, EXAMPLES, MAX_INPUT_LENGTH, _error_context, app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def page(client, formula=None):
    """GET the page, with an optional formula in the query string. Returns (status, html)."""
    query = None if formula is None else {"formula": formula}
    response = client.get("/", query_string=query)
    return response.status_code, response.get_data(as_text=True)


def table_row_count(html):
    return len(re.findall(r"<tr>", html))


def squash(html):
    """Collapse whitespace runs the way a browser does, to compare visible sentences."""
    return re.sub(r"\s+", " ", html)


# --- the empty page ---

def test_home_page_shows_form_and_examples(client):
    status, html = page(client)
    assert status == 200
    assert 'name="formula"' in html
    assert "Try an example" in html
    assert "<table" not in html
    assert "can't be computed" not in html


def test_symbol_buttons_are_hidden_until_javascript_runs(client):
    _, html = page(client)
    assert re.search(r'<div id="symbols"[^>]*\bhidden\b', html)
    for symbol in "¬∧∨→↔⊥":
        assert f'data-insert="{symbol}"' in html


@pytest.mark.parametrize("example", EXAMPLES)
def test_every_example_link_works(client, example):
    _, home = page(client)
    assert "formula=" in home                      # links exist
    status, html = page(client, example)
    assert status == 200
    assert "Result" in html
    assert "can't be computed" not in html


# --- a successful computation ---

def test_truth_table_page_for_implication(client):
    status, html = page(client, "P -> Q")
    assert status == 200
    assert "Read as: <code>P → Q</code>" in html
    assert 'class="badge contingency"' in html
    assert "3 of 4 rows are true." in squash(html)
    assert table_row_count(html) == 5              # header + 4 rows
    assert '<th scope="col">P</th>' in html
    assert '<th scope="col">Q</th>' in html
    assert '<th scope="col" class="formula-col">P → Q</th>' in html


def test_formula_stays_in_the_input_box(client):
    _, html = page(client, "P -> Q")
    assert 'value="P -&gt; Q"' in html


def test_result_cells_use_letters_not_just_colour(client):
    _, html = page(client, "P ∧ Q")
    cells = re.findall(r'<td class="(?:formula-col )?(yes|no)">([TF])</td>', html)
    assert cells                                    # found some
    assert all((cls == "yes") == (letter == "T") for cls, letter in cells)
    # last column of P ∧ Q is T, F, F, F
    assert re.findall(r'<td class="formula-col (?:yes|no)">([TF])</td>', html) == ["T", "F", "F", "F"]


@pytest.mark.parametrize("formula, badge, satisfiable_text", [
    ("P ∨ ¬P", "tautology", "Satisfiable."),
    ("P ∧ ¬P", "contradiction", "Not satisfiable."),
    ("P", "contingency", "Satisfiable."),
])
def test_classification_badges(client, formula, badge, satisfiable_text):
    _, html = page(client, formula)
    assert f'class="badge {badge}"' in html
    assert satisfiable_text in html


def test_zero_variable_formula(client):
    _, html = page(client, "¬⊥")
    assert table_row_count(html) == 2              # header + the single row
    assert "1 of 1 row is true." in squash(html)
    assert 'class="badge tautology"' in html


def test_rows_omitted_notice(client):
    formula = " ∧ ".join(f"v{i}" for i in range(9))
    status, html = page(client, formula)
    assert status == 200
    assert "The table is not shown: 9 variables make 512 rows." in squash(html)
    assert "<table" not in html
    assert 'class="badge contingency"' in html


# --- errors ---

def test_syntax_error_shows_message_and_caret(client):
    status, html = page(client, "P ∧")
    assert status == 200
    assert "That formula can't be computed" in html
    assert '<span class="line">P ∧</span>' in html
    assert '<span class="caret">   ^</span>' in html
    assert "UNEXPECTED_END" in html
    assert "position 3" in html
    assert "<table" not in html


def test_empty_submission_is_an_error_not_a_crash(client):
    status, html = page(client, "")
    assert status == 200
    assert "EMPTY_INPUT" in html


def test_limit_error_has_no_position_or_caret(client):
    formula = " ∧ ".join(f"v{i}" for i in range(17))
    status, html = page(client, formula)
    assert status == 200
    assert "LIMIT_EXCEEDED" in html
    assert "17 variables is too many" in html
    assert "caret" not in html
    assert not re.search(r"position \d", html)      # no "position N" line for this error


def test_input_too_long(client):
    status, html = page(client, "P" * (MAX_INPUT_LENGTH + 1))
    assert status == 200
    assert "INPUT_TOO_LONG" in html
    assert "caret" not in html


def test_input_at_the_length_limit_is_accepted(client):
    status, html = page(client, "P" * MAX_INPUT_LENGTH)
    assert status == 200
    assert "INPUT_TOO_LONG" not in html
    assert "Result" in html


@pytest.mark.parametrize("formula", [
    pytest.param("(" * 900, id="parentheses"),
    pytest.param("¬" * 900 + "P", id="negations"),
    pytest.param("P→" * 450 + "P", id="implication-chain"),
])
def test_deeply_nested_input_gives_a_clean_error(client, formula):
    status, html = page(client, formula)
    assert status == 200
    assert "TOO_DEEP" in html


# --- hostile input is escaped ---

@pytest.mark.parametrize("formula", [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "P ∧ <b>",
    "&lt;script&gt;",
])
def test_user_input_is_html_escaped(client, formula):
    status, html = page(client, formula)
    assert status == 200
    assert "<script>alert" not in html
    assert "<img" not in html
    assert "<b>" not in html
    assert "&lt;" in html or "&amp;" in html or "&#34;" in html


def test_error_message_quotes_are_escaped(client):
    # The engine echoes the offending character inside its message.
    _, html = page(client, "P ∧ <")
    assert "unexpected character &#39;&lt;&#39;" in html
    assert "character '<'" not in html


def test_templates_escape_every_value_they_print():
    """Render the page with hostile values in every slot, bypassing the engine.

    Today the engine never puts markup into its results, so the routes above
    cannot show a hole here. This test is what protects a later feature that
    echoes more user text.
    """
    hostile = "<i>x</i>"

    def render(result, error_context=None):
        with app.test_request_context("/"):
            return render_template(
                "index.html", text=hostile, result=result, error_context=error_context,
                examples=EXAMPLES, classification_help=CLASSIFICATION_HELP,
            )

    success = {
        "ok": True, "canonical": hostile, "display": hostile, "variables": [hostile], "row_count": 2,
        "true_count": 1, "classification": "contingency", "satisfiable": True,
        "rows_omitted": False,
        "rows": [{"assignment": {hostile: True}, "value": True},
                 {"assignment": {hostile: False}, "value": False}],
    }
    failure = {"ok": False, "error": {"code": hostile, "message": hostile, "position": 0}}

    assert "<i>" not in render(success)
    assert "<i>" not in render(failure, {"line": hostile, "caret": hostile})


# --- the caret helper ---

@pytest.mark.parametrize("text, position, line, caret", [
    ("P ∧", 3, "P ∧", "   ^"),
    ("P @ Q", 2, "P @ Q", "  ^"),
    ("a\tb", 2, "a b", "  ^"),            # tab becomes a space so the caret lines up
    ("a\nb", 2, "a b", "  ^"),
    ("¬¬ ∧", 3, "¬¬ ∧", "   ^"),          # non-ASCII characters count as one position each
    ("", 0, "", "^"),
])
def test_error_context(text, position, line, caret):
    assert _error_context(text, position) == {"line": line, "caret": caret}


def test_error_context_is_none_without_a_position():
    assert _error_context("P", None) is None


# --- routing ---

def test_post_is_not_allowed(client):
    assert client.post("/", data={"formula": "P"}).status_code == 405


def test_unknown_route_is_404(client):
    assert client.get("/nope").status_code == 404


@pytest.mark.parametrize("path", ["/static/style.css", "/static/app.js"])
def test_static_files_are_served(client, path):
    response = client.get(path)
    assert response.status_code == 200
    response.close()


def test_page_shows_explicit_grouping(client):
    _, html = page(client, "P → Q ∧ ¬R")
    assert "Read as: <code>P → (Q ∧ ¬R)</code>" in html
    assert '<th scope="col" class="formula-col">P → (Q ∧ ¬R)</th>' in html
