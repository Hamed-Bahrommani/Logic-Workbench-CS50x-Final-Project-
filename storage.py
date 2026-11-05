"""Anonymous attempt history, kept in SQLite.

A visitor is just a random id held in a signed cookie: no names, no emails.
Every query is parameterised, and old attempts are pruned so one visitor cannot
make the table grow without limit.
"""

import sqlite3
from contextlib import closing

MAX_ATTEMPTS_PER_EXERCISE = 50
STATUSES = ("complete", "unfinished", "errors")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    exercise_id  TEXT NOT NULL,
    proof_text   TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('complete', 'unfinished', 'errors')),
    error_count  INTEGER NOT NULL CHECK (error_count >= 0),
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS attempts_lookup ON attempts (session_id, exercise_id, id);
"""

_COLUMNS = "id, exercise_id, proof_text, status, error_count, created_at"


def _connect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(path) -> None:
    """Create the tables if they are not there yet. Safe to call every time."""
    with closing(_connect(path)) as connection, connection:
        connection.executescript(_SCHEMA)


def record_attempt(path, session_id, exercise_id, proof_text, status, error_count) -> int:
    """Store one attempt and return its id.

    Afterwards, only the newest MAX_ATTEMPTS_PER_EXERCISE attempts at this exercise
    are kept for this visitor, plus their most recent complete one, so a solved
    exercise stays solved however many later attempts they make.
    """
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, not {status!r}")
    with closing(_connect(path)) as connection, connection:
        cursor = connection.execute(
            "INSERT INTO attempts (session_id, exercise_id, proof_text, status, error_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, exercise_id, proof_text, status, error_count),
        )
        connection.execute(
            """
            DELETE FROM attempts
            WHERE session_id = ? AND exercise_id = ?
              AND id NOT IN (
                  SELECT id FROM attempts
                  WHERE session_id = ? AND exercise_id = ?
                  ORDER BY id DESC LIMIT ?
              )
              AND id != (
                  SELECT COALESCE(MAX(id), -1) FROM attempts
                  WHERE session_id = ? AND exercise_id = ? AND status = 'complete'
              )
            """,
            (session_id, exercise_id, session_id, exercise_id, MAX_ATTEMPTS_PER_EXERCISE,
             session_id, exercise_id),
        )
        return cursor.lastrowid


def attempts_for(path, session_id, exercise_id, limit=20) -> list[dict]:
    """This visitor's attempts at one exercise, newest first."""
    with closing(_connect(path)) as connection:
        rows = connection.execute(
            f"SELECT {_COLUMNS} FROM attempts "
            "WHERE session_id = ? AND exercise_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, exercise_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_attempt(path, session_id, exercise_id, attempt_id) -> dict | None:
    """One attempt, but only if it belongs to this visitor and this exercise."""
    with closing(_connect(path)) as connection:
        row = connection.execute(
            f"SELECT {_COLUMNS} FROM attempts "
            "WHERE id = ? AND session_id = ? AND exercise_id = ?",
            (attempt_id, session_id, exercise_id),
        ).fetchone()
    return dict(row) if row else None


def solved_exercises(path, session_id) -> set[str]:
    """The ids of the exercises this visitor has solved."""
    with closing(_connect(path)) as connection:
        rows = connection.execute(
            "SELECT DISTINCT exercise_id FROM attempts WHERE session_id = ? AND status = 'complete'",
            (session_id,),
        ).fetchall()
    return {row["exercise_id"] for row in rows}


def delete_session(path, session_id) -> int:
    """Forget everything about one visitor. Returns how many attempts were deleted."""
    with closing(_connect(path)) as connection, connection:
        cursor = connection.execute("DELETE FROM attempts WHERE session_id = ?", (session_id,))
        return cursor.rowcount
