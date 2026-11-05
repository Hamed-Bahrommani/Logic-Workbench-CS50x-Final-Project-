import re

import pytest

from app import MAX_INPUT_LENGTH, PROOF_EXAMPLES, app
from logic.proof import RULES


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def get(client, **params):
    response = client.get("/proof", query_string=params or None)
    return response.status_code, response.get_data(as_text=True)


def squash(html):
    return re.sub(r"\s+", " ", html)


def line_count(html, kind):
    return len(re.findall(rf'<li class="proof-line {kind}">', html))


def test_empty_page(client):
    status, html = get(client)
    assert status == 200
    assert 'name="premises"' in html
    assert 'name="conclusion"' in html
    assert 'name="proof"' in html
    assert "Try an example" in html
    assert '<ol class="proof-lines">' not in html


def test_rule_reference_lists_every_rule(client):
    _, html = get(client)
    for rule_id in RULES:
        assert f"<code>{rule_id}</code>" in html


@pytest.mark.parametrize(
    "example",
    [pytest.param(e, id=f"example-{n}") for n, e in enumerate(PROOF_EXAMPLES)],
)
def test_every_example_is_a_complete_proof(client, example):
    status, html = get(
        client, premises=example["premises"], conclusion=example["conclusion"],
        proof=example["proof"],
    )
    assert status == 200
    assert "Proof complete" in html
    assert line_count(html, "bad") == 0
    assert line_count(html, "ok") == len(example["proof"].splitlines())


def test_correct_but_unfinished(client):
    _, html = get(client, premises="P", conclusion="Q", proof="P ; premise")
    assert "Not finished" in html
    assert "last line is not the conclusion" in squash(html)
    assert "Proof complete" not in html


def test_one_error_is_singular(client):
    _, html = get(client, premises="P", conclusion="P", proof="P ; magic 1")
    assert "1 error" in html and "1 errors" not in html
    assert line_count(html, "bad") == 1


def test_two_errors_are_plural(client):
    _, html = get(client, premises="P", conclusion="P", proof="Q ; premise\nP ; magic 1")
    assert "2 errors" in html
    assert line_count(html, "bad") == 2


def test_line_error_shows_message_and_code(client):
    _, html = get(client, premises="P", conclusion="P", proof="P ; magic 1")
    assert "UNKNOWN_RULE" in html
    assert "unknown rule" in html


def test_syntax_error_in_a_line_shows_a_caret(client):
    _, html = get(client, premises="P", conclusion="P", proof="P ∧ ; premise")
    assert '<span class="line">P ∧</span>' in html
    assert '<span class="caret">   ^</span>' in html


def test_wrong_result_is_explained(client):
    _, html = get(
        client, premises="P → Q\nP", conclusion="Q",
        proof="P → Q ; premise\nP ; premise\nP ; ImpE 1,2",
    )
    assert "RESULT_MISMATCH" in html
    assert "gives Q" in squash(html)


def test_lines_are_shown_with_explicit_grouping(client):
    _, html = get(client, premises="P → Q ∧ R", conclusion="P → Q ∧ R", proof="P → Q ∧ R ; premise")
    assert "<code>P → (Q ∧ R)</code>" in html


def test_premise_error_names_its_field(client):
    _, html = get(client, premises="P ∧\nQ", conclusion="Q", proof="Q ; premise")
    assert "Problem in: <strong>Premise 1</strong>" in html
    assert '<span class="caret">   ^</span>' in html


def test_conclusion_error_names_its_field(client):
    _, html = get(client, premises="P", conclusion="→", proof="P ; premise")
    assert "Problem in: <strong>Conclusion</strong>" in html


def test_empty_proof_is_an_error(client):
    _, html = get(client, premises="P", conclusion="P", proof="")
    assert "EMPTY_PROOF" in html


def test_too_many_lines(client):
    _, html = get(client, premises="P", conclusion="P", proof="\n".join(["P ; premise"] * 101))
    assert "LIMIT_EXCEEDED" in html


def test_proof_text_too_long(client):
    _, html = get(client, premises="P", conclusion="P", proof="P ; premise\n" * 10000)
    assert "INPUT_TOO_LONG" in html
    assert "proof is too long" in html


def test_premise_too_long(client):
    _, html = get(client, premises="P" * (MAX_INPUT_LENGTH + 1), conclusion="P", proof="P ; premise")
    assert "INPUT_TOO_LONG" in html
    assert "Problem in: <strong>Premise 1</strong>" in html


def test_inputs_stay_in_their_boxes(client):
    _, html = get(client, premises="P → Q\nP", conclusion="Q",
                  proof="P → Q ; premise\nP ; premise\nQ ; ImpE 1,2")
    assert "P → Q\nP</textarea>" in html
    assert 'value="Q"' in html
    assert "Q ; ImpE 1,2</textarea>" in html


def test_hostile_input_is_escaped(client):
    _, html = get(client, premises="<b>", conclusion="<i>",
                  proof="<script>alert(1)</script> ; <img src=x>")
    assert "<script>alert" not in html
    assert "<img" not in html
    assert "<b>" not in html
    assert "<i>" not in html


def test_nav_marks_this_page(client):
    _, html = get(client)
    assert html.count('aria-current="page"') == 1
    assert re.search(r'<a href="/proof"[^>]*aria-current="page"', html)


def test_palette_and_formula_inputs(client):
    _, html = get(client)
    assert re.search(r'<div id="symbols"[^>]*\bhidden\b', html)
    assert len(re.findall(r'class="formula-input"', html)) == 3


def test_post_is_not_allowed(client):
    assert client.post("/proof", data={"proof": "P ; premise"}).status_code == 405

# --- subproofs ---

CONTRAPOSITION = "\n".join([
    "P → Q ; premise",
    "| ¬Q ; assume",
    "| | P ; assume",
    "| | Q ; ImpE 1,3",
    "| | ⊥ ; NotE 4,2",
    "| ¬P ; NotI 3-5",
    "¬Q → ¬P ; ImpI 2-6",
])


def test_nested_boxes_are_drawn_with_bars(client):
    _, html = get(client, premises="P → Q", conclusion="¬Q → ¬P", proof=CONTRAPOSITION)
    assert "Proof complete" in html
    assert '<span class="bars" aria-hidden="true">│ │ </span>' in html
    assert '<span class="bars" aria-hidden="true"></span>' in html     # depth-0 lines


def test_ranges_are_shown_in_the_rule_column(client):
    _, html = get(client, premises="P → Q", conclusion="¬Q → ¬P", proof=CONTRAPOSITION)
    assert "NotI 3-5" in html
    assert "ImpI 2-6" in html


def test_ending_inside_a_subproof_is_explained(client):
    _, html = get(client, premises="", conclusion="P", proof="| P ; assume")
    assert "Not finished" in html
    assert "inside a subproof" in squash(html)
    assert "Proof complete" not in html


def test_scope_error_is_shown_on_its_line(client):
    _, html = get(client, premises="", conclusion="P",
                  proof="| P ; assume\nP → P ; ImpI 1-1\nP ; R 1")
    assert "OUT_OF_SCOPE" in html
    assert "1 error" in html
    assert line_count(html, "bad") == 1


def test_indentation_error_is_shown(client):
    _, html = get(client, premises="", conclusion="P", proof="P ; Assume")
    assert "BAD_INDENT" in html


@pytest.mark.parametrize("rule_id", ["Assume", "ImpI", "NotI", "IffI", "OrE"])
def test_rule_reference_lists_the_box_rules(client, rule_id):
    _, html = get(client)
    assert f"<code>{rule_id}</code>" in html
