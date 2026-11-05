"""The exercise list: loading and structural validation of exercises.json.

Checking that each exercise is a valid argument, and that its stored solution
really is a complete proof, is done by the test suite and not here, so a typo in
the data cannot stop the site from starting.
"""

import json
import re
from pathlib import Path

EXERCISES_PATH = Path(__file__).with_name("exercises.json")

LEVELS = {1: "Line rules only", 2: "Subproofs", 3: "Challenges"}

_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_FIELDS = {"id", "title", "level", "premises", "conclusion", "hint", "solution"}


def _nonempty_string(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_exercises(path=EXERCISES_PATH) -> list[dict]:
    """Read and validate the exercise file. Raises ValueError with a clear message."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ValueError(f"cannot read exercises: {err}") from err
    if not isinstance(data, list):
        raise ValueError("the exercise file must be a list")

    exercises = []
    seen = set()
    for index, raw in enumerate(data, start=1):
        where = f"exercise {index}"
        if not isinstance(raw, dict):
            raise ValueError(f"{where}: must be an object")
        missing = _FIELDS - raw.keys()
        if missing:
            raise ValueError(f"{where}: missing {sorted(missing)}")
        extra = raw.keys() - _FIELDS
        if extra:
            raise ValueError(f"{where}: unknown keys {sorted(extra)}")

        identifier = raw["id"]
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            raise ValueError(f"{where}: bad id {identifier!r} (use lowercase words joined by '-')")
        where = f"exercise {identifier!r}"
        if identifier in seen:
            raise ValueError(f"{where}: duplicate id")
        seen.add(identifier)

        level = raw["level"]
        if isinstance(level, bool) or level not in LEVELS:
            raise ValueError(f"{where}: level must be one of {sorted(LEVELS)}")
        for field in ("title", "conclusion", "hint"):
            if not _nonempty_string(raw[field]):
                raise ValueError(f"{where}: {field} must be a non-empty string")
        premises = raw["premises"]
        if not isinstance(premises, list) or not all(_nonempty_string(p) for p in premises):
            raise ValueError(f"{where}: premises must be a list of non-empty strings")
        solution = raw["solution"]
        if not isinstance(solution, list) or not solution or not all(_nonempty_string(s) for s in solution):
            raise ValueError(f"{where}: solution must be a non-empty list of non-empty strings")

        exercises.append({
            "id": identifier,
            "title": raw["title"],
            "level": level,
            "premises": list(premises),
            "premises_text": "\n".join(premises),
            "conclusion": raw["conclusion"],
            "hint": raw["hint"],
            "solution": list(solution),
            "solution_text": "\n".join(solution),
        })
    return exercises
