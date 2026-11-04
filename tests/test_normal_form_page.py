import re

import pytest

from app import MAX_INPUT_LENGTH, NORMAL_FORM_EXAMPLES, app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def get(client, **params):
    response = client.get("/normal-form", query_string=params or None)
    return response.status_code, response.get_data(as_text=True)


def squash(html):
    return re.sub(r"\s+", " ", html)


def step_count(html):
    return len(re.findall(r'<li class="step">', html))


def test_empty_page(client):
    status, html = get(client)
    assert status == 200
    assert 'name="formula"' in html
    assert 'name="strategy"' in html
    assert "Try an example" in html
    assert '<ol class="steps">' not in html
    assert "can't be computed" not in html


def test_default_target_is_cnf(client):
    _, html = get(client)
    assert '<option value="cnf" selected>' in html
    assert "selected>" in html and html.count("selected>") == 1


@pytest.mark.parametrize("strategy", ["nnf", "cnf", "dnf"])
def test_selected_strategy_stays_selected(client, strategy):
    _, html = get(client, formula="P", strategy=strategy)
    assert f'<option value="{strategy}" selected>' in html
    assert html.count("selected>") == 1


@pytest.mark.parametrize(
    "example",
    [pytest.param(e, id=f"example-{n}") for n, e in enumerate(NORMAL_FORM_EXAMPLES)],
)
def test_examples_work(client, example):
    status, html = get(client, formula=example["formula"], strategy=example["strategy"])
    assert status == 200
    assert "Result" in html
    assert "can't be computed" not in html


def test_cnf_rewrite_shows_the_law_and_the_result(client):
    _, html = get(client, formula="(P ∧ Q) ∨ R", strategy="cnf")
    assert step_count(html) == 1
    assert "Distribute ∨ over ∧" in html
    assert "Start: <code>(P ∧ Q) ∨ R</code>" in html
    assert "Result: <code>(P ∨ R) ∧ (Q ∨ R)</code>" in html


def test_steps_show_the_statement_of_each_law(client):
    _, html = get(client, formula="¬(P → Q)", strategy="nnf")
    text = squash(html)
    assert step_count(html) == 3
    assert "Rewritten in 3 steps." in text
    assert "Eliminate →" in text
    assert "De Morgan (∨)" in text
    assert "¬¬A ≡ A" in text
    assert "Result: <code>P ∧ ¬Q</code>" in text


def test_single_step_is_not_pluralised(client):
    _, html = get(client, formula="P → Q", strategy="nnf")
    assert "Rewritten in 1 step." in squash(html)


def test_formula_already_in_the_form(client):
    _, html = get(client, formula="P ∧ ¬Q", strategy="cnf")
    assert "already in conjunctive normal form" in squash(html)
    assert '<ol class="steps">' not in html
    assert "Result: <code>P ∧ ¬Q</code>" in html


def test_formula_stays_in_the_input_box(client):
    _, html = get(client, formula="P -> Q", strategy="nnf")
    assert 'value="P -&gt; Q"' in html


def test_syntax_error_shows_the_caret(client):
    status, html = get(client, formula="P ∧", strategy="cnf")
    assert status == 200
    assert "UNEXPECTED_END" in html
    assert '<span class="caret">   ^</span>' in html
    assert '<ol class="steps">' not in html


def test_empty_formula_is_an_error(client):
    _, html = get(client, formula="", strategy="cnf")
    assert "EMPTY_INPUT" in html


def test_unknown_strategy_is_an_error_not_a_crash(client):
    status, html = get(client, formula="P", strategy="xyz")
    assert status == 200
    assert "UNKNOWN_STRATEGY" in html


def test_input_too_long(client):
    _, html = get(client, formula="P" * (MAX_INPUT_LENGTH + 1), strategy="cnf")
    assert "INPUT_TOO_LONG" in html
    assert "caret" not in html


def test_blow_up_is_a_clean_limit_error(client):
    formula = " ∧ ".join(f"(a{i} ∨ b{i})" for i in range(8))
    status, html = get(client, formula=formula, strategy="dnf")
    assert status == 200
    assert "LIMIT_EXCEEDED" in html
    assert "caret" not in html


def test_hostile_input_is_escaped(client):
    _, html = get(client, formula="<script>alert(1)</script>", strategy="cnf")
    assert "<script>alert" not in html


def test_nav_marks_this_page(client):
    _, html = get(client)
    assert html.count('aria-current="page"') == 1
    assert re.search(r'<a href="/normal-form"[^>]*aria-current="page"', html)


def test_palette_and_input_class(client):
    _, html = get(client)
    assert re.search(r'<div id="symbols"[^>]*\bhidden\b', html)
    assert len(re.findall(r'class="formula-input"', html)) == 1


def test_post_is_not_allowed(client):
    assert client.post("/normal-form", data={"formula": "P"}).status_code == 405
