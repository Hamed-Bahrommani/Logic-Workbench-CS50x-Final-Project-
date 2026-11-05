import re
import sqlite3

import pytest

import storage


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    storage.init_db(path)
    return path


def record(db, session="s1", exercise="ex", text="P ; premise", status="errors", errors=1):
    return storage.record_attempt(db, session, exercise, text, status, errors)


def test_init_is_idempotent(tmp_path):
    path = tmp_path / "again.db"
    storage.init_db(path)
    storage.init_db(path)
    assert storage.attempts_for(path, "nobody", "ex") == []


def test_record_and_read_back_newest_first(db):
    first = record(db, text="one")
    second = record(db, text="two")
    assert second > first
    rows = storage.attempts_for(db, "s1", "ex")
    assert [row["proof_text"] for row in rows] == ["two", "one"]
    assert set(rows[0]) == {"id", "exercise_id", "proof_text", "status", "error_count", "created_at"}
    assert rows[0]["status"] == "errors" and rows[0]["error_count"] == 1


def test_created_at_is_a_utc_timestamp(db):
    record(db)
    [row] = storage.attempts_for(db, "s1", "ex")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["created_at"])


def test_limit_parameter(db):
    for n in range(5):
        record(db, text=f"attempt {n}")
    assert len(storage.attempts_for(db, "s1", "ex", limit=3)) == 3


def test_visitors_cannot_see_each_others_attempts(db):
    attempt = record(db, session="alice")
    assert storage.attempts_for(db, "bob", "ex") == []
    assert storage.get_attempt(db, "bob", "ex", attempt) is None
    assert storage.get_attempt(db, "alice", "ex", attempt)["id"] == attempt


def test_an_attempt_is_only_found_under_its_own_exercise(db):
    attempt = record(db, exercise="ex")
    assert storage.get_attempt(db, "s1", "other", attempt) is None


def test_solved_exercises_counts_only_complete_attempts(db):
    record(db, exercise="a", status="errors")
    record(db, exercise="b", status="unfinished", errors=0)
    record(db, exercise="c", status="complete", errors=0)
    record(db, session="s2", exercise="d", status="complete", errors=0)
    assert storage.solved_exercises(db, "s1") == {"c"}
    assert storage.solved_exercises(db, "s2") == {"d"}
    assert storage.solved_exercises(db, "nobody") == set()


def test_unknown_status_is_refused_and_nothing_is_stored(db):
    with pytest.raises(ValueError):
        record(db, status="great")
    assert storage.attempts_for(db, "s1", "ex") == []


def test_the_database_itself_refuses_bad_rows(db):
    connection = sqlite3.connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO attempts (session_id, exercise_id, proof_text, status, error_count) "
            "VALUES ('s', 'e', 't', 'bogus', 0)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO attempts (session_id, exercise_id, proof_text, status, error_count) "
            "VALUES ('s', 'e', 't', 'errors', -1)"
        )
    connection.close()


def test_old_attempts_are_pruned(db):
    first = record(db, text="oldest")
    for n in range(storage.MAX_ATTEMPTS_PER_EXERCISE + 9):
        record(db, text=f"later {n}")
    rows = storage.attempts_for(db, "s1", "ex", limit=1000)
    assert len(rows) == storage.MAX_ATTEMPTS_PER_EXERCISE
    assert first not in [row["id"] for row in rows]
    assert rows[0]["proof_text"] == f"later {storage.MAX_ATTEMPTS_PER_EXERCISE + 8}"


def test_a_solved_exercise_stays_solved_after_pruning(db):
    record(db, text="the solution", status="complete", errors=0)
    for n in range(storage.MAX_ATTEMPTS_PER_EXERCISE + 9):
        record(db, text=f"later {n}")
    assert storage.solved_exercises(db, "s1") == {"ex"}
    rows = storage.attempts_for(db, "s1", "ex", limit=1000)
    assert len(rows) == storage.MAX_ATTEMPTS_PER_EXERCISE + 1
    assert rows[-1]["proof_text"] == "the solution"


def test_pruning_does_not_touch_other_exercises_or_visitors(db):
    other_exercise = record(db, exercise="keep-me")
    other_visitor = record(db, session="s2")
    for n in range(storage.MAX_ATTEMPTS_PER_EXERCISE + 5):
        record(db, text=f"later {n}")
    assert storage.get_attempt(db, "s1", "keep-me", other_exercise) is not None
    assert storage.get_attempt(db, "s2", "ex", other_visitor) is not None


def test_delete_session_removes_only_that_visitor(db):
    record(db, session="alice")
    record(db, session="alice", exercise="other")
    record(db, session="bob")
    assert storage.delete_session(db, "alice") == 2
    assert storage.attempts_for(db, "alice", "ex") == []
    assert len(storage.attempts_for(db, "bob", "ex")) == 1
    assert storage.delete_session(db, "alice") == 0


def test_hostile_values_are_stored_as_plain_data(db):
    nasty_session = "x' OR '1'='1"
    nasty_text = "P ; premise\n'); DROP TABLE attempts; --\n⊥ ∧ \"quotes\""
    attempt = record(db, session=nasty_session, exercise="e' --", text=nasty_text)
    record(db, session="innocent")
    rows = storage.attempts_for(db, nasty_session, "e' --")
    assert [row["proof_text"] for row in rows] == [nasty_text]
    assert storage.get_attempt(db, nasty_session, "e' --", attempt)["proof_text"] == nasty_text
    assert len(storage.attempts_for(db, "innocent", "ex")) == 1      # the table still exists
