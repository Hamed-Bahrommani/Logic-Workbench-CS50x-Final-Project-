import re

import pytest
from markupsafe import escape

from app import EXERCISES, MAX_PROOF_TEXT, app
from exercises import LEVELS

MODUS_PONENS = next(e for e in EXERCISES if e["id"] == "modus-ponens")


@pytest.fixture
def client(tmp_path):
    original = app.config["DATABASE"]
    app.config.update(TESTING=True, DATABASE=str(tmp_path / "test.db"))
    yield app.test_client()
    app.config["DATABASE"] = original


def squash(html):
    return re.sub(r"\s+", " ", html)


def page(client, path):
    response = client.get(path)
    return response.status_code, response.get_data(as_text=True)


def token(client, path="/exercises/modus-ponens"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)


def submit(client, exercise_id, proof, follow=True, csrf=None):
    return client.post(
        f"/exercises/{exercise_id}",
        data={"proof": proof, "csrf": csrf or token(client, f"/exercises/{exercise_id}")},
        follow_redirects=follow,
    )


def html_of(response):
    return response.get_data(as_text=True)


# --- the list ---

def test_list_shows_every_exercise_grouped_by_level(client):
    status, html = page(client, "/exercises")
    assert status == 200
    for level_name in LEVELS.values():
        assert level_name in html
    for exercise in EXERCISES:
        assert f'href="/exercises/{exercise["id"]}"' in html
    assert f"0 of {len(EXERCISES)} solved" in squash(html)


def test_a_new_visitor_has_nothing_to_forget(client):
    _, html = page(client, "/exercises")
    assert "Forget my history" not in html


def test_nav_marks_the_exercise_pages(client):
    for path in ("/exercises", "/exercises/modus-ponens"):
        _, html = page(client, path)
        assert html.count('aria-current="page"') == 1
        assert re.search(r'<a href="/exercises"[^>]*aria-current="page"', html)


# --- one exercise ---

def test_exercise_page_shows_the_task(client):
    status, html = page(client, "/exercises/modus-ponens")
    assert status == 200
    assert "<code>P → Q</code>" in html
    assert "Goal: <code>Q</code>" in html
    assert str(escape(MODUS_PONENS["hint"])) in html
    assert str(escape(MODUS_PONENS["solution_text"])) in html
    assert '<form method="post"' in html
    assert 'name="csrf"' in html
    assert "Your attempts" not in html
    assert 'id="result-heading"' not in html


def test_exercise_page_has_the_symbol_palette_and_one_input(client):
    _, html = page(client, "/exercises/modus-ponens")
    assert re.search(r'<div id="symbols"[^>]*\bhidden\b', html)
    assert len(re.findall(r'class="formula-input"', html)) == 1


def test_exercise_without_premises(client):
    _, html = page(client, "/exercises/self-implication")
    assert "No premises." in html


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e["id"])
def test_every_exercise_page_renders(client, exercise):
    status, html = page(client, f"/exercises/{exercise['id']}")
    assert status == 200
    assert str(escape(exercise["title"])) in html
    assert str(escape(exercise["solution_text"])) in html


def test_unknown_exercise_is_404(client):
    assert client.get("/exercises/nope").status_code == 404
    assert client.post("/exercises/nope", data={"proof": "P ; premise"}).status_code == 404


# --- submitting ---

@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e["id"])
def test_every_stored_solution_is_accepted_end_to_end(client, exercise):
    response = submit(client, exercise["id"], exercise["solution_text"])
    assert response.status_code == 200
    assert "Proof complete" in html_of(response)


def test_submitting_redirects_so_a_refresh_cannot_resubmit(client):
    response = submit(client, "modus-ponens", MODUS_PONENS["solution_text"], follow=False)
    assert response.status_code == 303
    assert "/exercises/modus-ponens?attempt=1" in response.headers["Location"]


def test_a_solved_exercise_is_marked_and_offers_the_next_one(client):
    response = submit(client, "modus-ponens", MODUS_PONENS["solution_text"])
    html = html_of(response)
    assert "Next exercise:" in html
    _, listing = page(client, "/exercises")
    assert f"1 of {len(EXERCISES)} solved" in squash(listing)
    assert listing.count("Solved: ") == 1


def test_a_wrong_proof_is_recorded_but_does_not_count_as_solved(client):
    response = submit(client, "modus-ponens", "Q ; premise")
    html = html_of(response)
    assert "NOT_A_PREMISE" in html
    assert "1 error" in html
    _, listing = page(client, "/exercises")
    assert f"0 of {len(EXERCISES)} solved" in squash(listing)


def test_a_correct_but_unfinished_proof(client):
    html = html_of(submit(client, "modus-ponens", "P → Q ; premise"))
    assert "Not finished" in html
    assert "correct so far" in html


def test_history_lists_attempts_newest_first_with_links(client):
    submit(client, "modus-ponens", "Q ; premise")
    submit(client, "modus-ponens", MODUS_PONENS["solution_text"])
    _, html = page(client, "/exercises/modus-ponens")
    links = re.findall(r'href="/exercises/modus-ponens\?attempt=(\d+)"', html)
    assert links == ["2", "1"]


def test_the_last_attempt_is_prefilled(client):
    submit(client, "modus-ponens", "Q ; premise")
    _, html = page(client, "/exercises/modus-ponens")
    assert "Q ; premise</textarea>" in html
    assert 'id="result-heading"' not in html          # prefilled, but not re-judged


def test_an_old_attempt_can_be_reopened(client):
    submit(client, "modus-ponens", "Q ; premise")
    submit(client, "modus-ponens", MODUS_PONENS["solution_text"])
    _, html = page(client, "/exercises/modus-ponens?attempt=1")
    assert "NOT_A_PREMISE" in html
    assert "Q ; premise</textarea>" in html


def test_empty_proof_is_not_recorded(client):
    response = submit(client, "modus-ponens", "")
    assert response.status_code == 200
    assert "EMPTY_PROOF" in html_of(response)
    _, html = page(client, "/exercises/modus-ponens")
    assert "Your attempts" not in html


def test_oversized_proof_is_not_recorded(client):
    response = submit(client, "modus-ponens", "P ; premise\n" * (MAX_PROOF_TEXT // 10))
    assert "INPUT_TOO_LONG" in html_of(response)
    _, html = page(client, "/exercises/modus-ponens")
    assert "Your attempts" not in html


def test_hostile_proof_text_is_escaped_everywhere(client):
    response = submit(client, "modus-ponens", "<script>alert(1)</script> ; <img src=x>")
    html = html_of(response)
    assert "<script>alert" not in html
    assert "<img" not in html
    _, again = page(client, "/exercises/modus-ponens")
    assert "<script>alert" not in again


# --- who can see what ---

def test_attempt_ids_are_private_to_the_visitor(client):
    submit(client, "modus-ponens", "Q ; premise")
    stranger = app.test_client()
    assert stranger.get("/exercises/modus-ponens?attempt=1").status_code == 404


def test_an_attempt_belongs_to_one_exercise(client):
    submit(client, "modus-ponens", "Q ; premise")
    assert client.get("/exercises/and-commutes?attempt=1").status_code == 404


def test_unknown_or_malformed_attempt_ids(client):
    submit(client, "modus-ponens", "Q ; premise")
    assert client.get("/exercises/modus-ponens?attempt=999").status_code == 404
    assert client.get("/exercises/modus-ponens?attempt=abc").status_code == 200


# --- CSRF, cookies, forgetting ---

def test_posting_without_a_token_is_refused(client):
    assert client.post("/exercises/modus-ponens", data={"proof": "P ; premise"}).status_code == 400


def test_posting_with_a_wrong_token_is_refused(client):
    token(client)
    response = client.post("/exercises/modus-ponens", data={"proof": "P ; premise", "csrf": "nope"})
    assert response.status_code == 400


def test_a_non_ascii_token_is_refused_not_a_crash(client):
    token(client)
    response = client.post("/exercises/modus-ponens", data={"proof": "P ; premise", "csrf": "é"})
    assert response.status_code == 400


def test_session_cookie_is_httponly_and_samesite(client):
    response = client.get("/exercises/modus-ponens")
    cookies = " ".join(response.headers.getlist("Set-Cookie"))
    assert "HttpOnly" in cookies
    assert "SameSite=Lax" in cookies


def test_forgetting_removes_the_history(client):
    submit(client, "modus-ponens", MODUS_PONENS["solution_text"])
    _, listing = page(client, "/exercises")
    assert "Forget my history" in listing
    response = client.post("/forget", data={"csrf": token(client, "/exercises")})
    assert response.status_code == 303
    _, after = page(client, "/exercises")
    assert f"0 of {len(EXERCISES)} solved" in squash(after)
    assert "Forget my history" not in after
    assert client.get("/exercises/modus-ponens?attempt=1").status_code == 404


def test_forgetting_needs_a_token(client):
    submit(client, "modus-ponens", MODUS_PONENS["solution_text"])
    assert client.post("/forget", data={}).status_code == 400
    _, listing = page(client, "/exercises")
    assert f"1 of {len(EXERCISES)} solved" in squash(listing)


def test_forget_is_post_only(client):
    assert client.get("/forget").status_code == 405