"""A checker for natural-deduction proofs with subproofs.

A proof is a list of lines "formula ; rule citations". A leading "|" per level
marks how deeply a line is nested. Each line is checked on its own against the
lines it cites; the checker never searches for a proof and never guesses what
a student meant.

Scope: a line may cite any earlier line in its own box or an enclosing box. A
closed box can only be cited as a whole, as a range "first-last".
"""

import re
from typing import Callable, NamedTuple

from logic.errors import FormulaError
from logic.nodes import And, Bot, Iff, Imp, Not, Or
from logic.parser import parse
from logic.printer import to_string

MAX_PROOF_LINES = 100

_NUMBER_PREFIX = re.compile(r"^\d+\s*[.)]\s+")
_BARS = re.compile(r"^(?:\|\s*)+")


class Entry(NamedTuple):
    formula_text: str
    justification: str | None     # None if the line has no ';'
    depth: int = 0                # how many leading '|' the line had


class Rule(NamedTuple):
    id: str
    arity: int
    statement: str
    check: Callable    # (cited formulas, result, premises) -> None, or (code, message)


class SubRule(NamedTuple):
    id: str
    kinds: tuple       # the kinds of citation it takes, in any order
    usage: str
    statement: str
    check: Callable    # (cited lines, cited ranges, result) -> None, or (code, message)


def _show(formula) -> str:
    return to_string(formula, explicit=True)


def _unique(items):
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _from_candidates(label, candidates, result, hint):
    if not candidates:
        return ("RULE_PATTERN", hint)
    if result in candidates:
        return None
    options = " or ".join(_show(c) for c in candidates)
    return ("RESULT_MISMATCH", f"{label} here gives {options}, not {_show(result)}")


# --- the line rules (they cite single lines) ----------------------------------------

def _premise(cited, result, premises):
    if result in premises:
        return None
    return ("NOT_A_PREMISE", f"{_show(result)} is not one of the premises")


def _and_i(cited, result, premises):
    a, b = cited
    return _from_candidates("∧I", _unique([And(a, b), And(b, a)]), result, "")


def _and_e(cited, result, premises):
    (a,) = cited
    candidates = [a.left, a.right] if isinstance(a, And) else []
    return _from_candidates(
        "∧E", _unique(candidates), result,
        f"∧E needs a conjunction A ∧ B, but {_show(a)} is not one",
    )


def _or_i(cited, result, premises):
    (a,) = cited
    if isinstance(result, Or) and (result.left == a or result.right == a):
        return None
    return (
        "RESULT_MISMATCH",
        f"∨I needs a disjunction with {_show(a)} as one of its sides, not {_show(result)}",
    )


def _imp_e(cited, result, premises):
    a, b = cited
    candidates = [x.right for x, y in ((a, b), (b, a)) if isinstance(x, Imp) and x.left == y]
    return _from_candidates(
        "→E", _unique(candidates), result,
        "→E needs an implication A → B and a line that is exactly A",
    )


def _iff_e(cited, result, premises):
    a, b = cited
    candidates = []
    for x, y in ((a, b), (b, a)):
        if isinstance(x, Iff):
            if x.left == y:
                candidates.append(x.right)
            if x.right == y:
                candidates.append(x.left)
    return _from_candidates(
        "↔E", _unique(candidates), result,
        "↔E needs a biconditional A ↔ B and a line that is exactly A or exactly B",
    )


def _not_e(cited, result, premises):
    a, b = cited
    candidates = [Bot()] if (a == Not(b) or b == Not(a)) else []
    return _from_candidates("¬E", candidates, result, "¬E needs a formula A and its negation ¬A")


def _bot_e(cited, result, premises):
    (a,) = cited
    if isinstance(a, Bot):
        return None
    return ("RULE_PATTERN", f"⊥E needs the line ⊥, but {_show(a)} is not ⊥")


def _dne(cited, result, premises):
    (a,) = cited
    candidates = [a.child.child] if isinstance(a, Not) and isinstance(a.child, Not) else []
    return _from_candidates(
        "¬¬E", candidates, result,
        f"¬¬E needs a double negation ¬¬A, but {_show(a)} is not one",
    )


def _reiterate(cited, result, premises):
    return _from_candidates("R", [cited[0]], result, "")


RULES = {
    rule.id: rule
    for rule in [
        Rule("premise", 0, "A line that is one of the argument's premises", _premise),
        Rule("AndI", 2, "From A and B, conclude A ∧ B", _and_i),
        Rule("AndE", 1, "From A ∧ B, conclude A (or conclude B)", _and_e),
        Rule("OrI", 1, "From A, conclude A ∨ B (or B ∨ A) for any B", _or_i),
        Rule("ImpE", 2, "From A → B and A, conclude B", _imp_e),
        Rule("IffE", 2, "From A ↔ B and A, conclude B; from A ↔ B and B, conclude A", _iff_e),
        Rule("NotE", 2, "From A and ¬A, conclude ⊥", _not_e),
        Rule("BotE", 1, "From ⊥, conclude any formula", _bot_e),
        Rule("DNE", 1, "From ¬¬A, conclude A", _dne),
        Rule("R", 1, "Repeat an earlier line", _reiterate),
    ]
}


# --- the subproof rules ----------------------------------------------------------------

ASSUME = Rule(
    "Assume", 0,
    "Open a box by assuming any formula (start the line with '|')",
    lambda cited, result, premises: None,
)


def _imp_i(lines, ranges, result):
    ((assumption, last),) = ranges
    return _from_candidates("→I", [Imp(assumption, last)], result, "")


def _not_i(lines, ranges, result):
    ((assumption, last),) = ranges
    if not isinstance(last, Bot):
        return ("RULE_PATTERN", f"¬I needs a subproof that ends in ⊥, but it ends in {_show(last)}")
    return _from_candidates("¬I", [Not(assumption)], result, "")


def _iff_i(lines, ranges, result):
    (a, b), (c, d) = ranges
    if not (b == c and d == a):
        return (
            "RULE_PATTERN",
            "↔I needs two subproofs: one assuming A and ending in B, the other assuming B and ending in A",
        )
    return _from_candidates("↔I", _unique([Iff(a, b), Iff(b, a)]), result, "")


def _or_e(lines, ranges, result):
    (disjunction,) = lines
    if not isinstance(disjunction, Or):
        return ("RULE_PATTERN", f"∨E needs a disjunction A ∨ B, but {_show(disjunction)} is not one")
    (first_assumption, first_last), (second_assumption, second_last) = ranges
    sides = (disjunction.left, disjunction.right)
    if (first_assumption, second_assumption) != sides and (second_assumption, first_assumption) != sides:
        return ("RULE_PATTERN", f"the two subproofs must assume the two sides of {_show(disjunction)}")
    if first_last != second_last:
        return (
            "RULE_PATTERN",
            "both subproofs must end in the same formula, but they end in "
            f"{_show(first_last)} and {_show(second_last)}",
        )
    return _from_candidates("∨E", [first_last], result, "")


SUBPROOF_RULES = {
    rule.id: rule
    for rule in [
        SubRule("ImpI", ("range",), "one subproof range, such as 2-4",
                "From a subproof that assumes A and ends in B, conclude A → B", _imp_i),
        SubRule("NotI", ("range",), "one subproof range, such as 2-4",
                "From a subproof that assumes A and ends in ⊥, conclude ¬A", _not_i),
        SubRule("IffI", ("range", "range"), "two subproof ranges, such as 2-4,5-7",
                "From a subproof A…B and a subproof B…A, conclude A ↔ B", _iff_i),
        SubRule("OrE", ("line", "range", "range"),
                "a disjunction line and two subproof ranges, such as 1,2-3,4-5",
                "From A ∨ B, a subproof A…C and a subproof B…C, conclude C", _or_e),
    ]
}

# Everything a student may write, for the rule reference on the page.
ALL_RULES = list(RULES.values()) + [ASSUME] + list(SUBPROOF_RULES.values())

_ALIAS_SPEC = {
    "AndI": ["∧I", "&I"], "AndE": ["∧E", "&E"], "OrI": ["∨I", "|I"],
    "ImpE": ["→E", "->E"], "IffE": ["↔E", "<->E"], "NotE": ["¬E", "~E"],
    "BotE": ["⊥E", "_|_E"], "DNE": ["¬¬E", "~~E"], "R": ["Reit"],
    "Assume": ["Hyp"], "ImpI": ["→I", "->I"], "NotI": ["¬I", "~I"],
    "IffI": ["↔I", "<->I"], "OrE": ["∨E", "|E"],
}

# Rule names are case-insensitive; every rule also has symbol and ASCII spellings.
_RULE_LOOKUP = {rule.id.lower(): rule for rule in ALL_RULES}
for _rule_id, _names in _ALIAS_SPEC.items():
    for _name in _names:
        _RULE_LOOKUP[_name.lower()] = next(r for r in ALL_RULES if r.id == _rule_id)


# --- reading the proof text -----------------------------------------------------------

def split_proof_text(text: str) -> list[Entry]:
    """Split proof text into one Entry per non-blank line."""
    entries = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = _NUMBER_PREFIX.sub("", line, count=1)
        depth = 0
        bars = _BARS.match(line)
        if bars:
            depth = bars.group().count("|")
            line = line[bars.end():]
        formula, separator, justification = line.rpartition(";")
        if separator:
            entries.append(Entry(formula.strip(), justification.strip(), depth))
        else:
            entries.append(Entry(line.strip(), None, depth))
    return entries


def _parse_citations(text):
    """Returns (items, bad token). An item is ("line", n) or ("range", first, last)."""
    items = []
    for token in text.replace(",", " ").split():
        if re.fullmatch(r"[0-9]+", token):
            items.append(("line", int(token)))
            continue
        match = re.fullmatch(r"([0-9]+)[-–]([0-9]+)", token)
        if match is None:
            return None, token
        items.append(("range", int(match.group(1)), int(match.group(2))))
    return items, None


# --- scope ----------------------------------------------------------------------------

class _Scope:
    """Which boxes are open, and which lines may be cited from where."""

    def __init__(self):
        self.stack = []     # ids of the open boxes, outermost first (a box's id is its Assume line)
        self.boxes = {}     # id -> {"parent": tuple of ids, "last": last line number}
        self.paths = []     # for each line, the tuple of boxes it sits in

    def enter(self, number, depth, opens_box):
        """Place line `number`. Returns a message if its indentation is wrong."""
        problem = None
        current = len(self.stack)
        if opens_box:
            if depth == 0:
                problem = "an Assume must be inside a box: start the line with '|'"
            elif depth > current + 1:
                problem = "a box can only be opened one level deeper than the line before it"
            effective = min(max(depth, 1), current + 1)
            del self.stack[effective - 1:]
            self.boxes[number] = {"parent": tuple(self.stack), "last": number}
            self.stack.append(number)
        else:
            if depth > current:
                problem = "this line is indented, but no Assume opened a box"
            del self.stack[min(depth, current):]
        for box in self.stack:
            self.boxes[box]["last"] = number
        self.paths.append(tuple(self.stack))
        return problem

    def can_see(self, ref, number):
        """May line `number` cite the single line `ref`?"""
        path = self.paths[ref - 1]
        return self.paths[number - 1][:len(path)] == path

    def resolve_range(self, start, end, number, parsed):
        """The (assumption, last line) of box start-end, or (None, error)."""
        box = self.boxes.get(start)
        if box is None or start >= number:
            return None, _error("BAD_RANGE", f"line {start} is not the first line of a subproof")
        current = self.paths[number - 1]
        if start in current:
            return None, _error(
                "OUT_OF_SCOPE", f"the subproof {start}-{end} is still open; close it before citing it"
            )
        if current[:len(box["parent"])] != box["parent"]:
            return None, _error(
                "OUT_OF_SCOPE",
                f"the subproof {start}-{end} is inside another subproof that has closed",
            )
        if box["last"] != end:
            return None, _error(
                "BAD_RANGE",
                f"the subproof that starts at line {start} ends at line {box['last']}, not {end}",
            )
        assumption, last = parsed[start - 1], parsed[end - 1]
        if assumption is None or last is None:
            return None, _error(
                "BAD_REFERENCE", f"a line in subproof {start}-{end} has an error in its formula"
            )
        return (assumption, last), None


# --- checking ---------------------------------------------------------------------------

def _error(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _display_refs(items):
    return [item[1] if item[0] == "line" else f"{item[1]}-{item[2]}" for item in items]


def _check_line(number, entry, parsed, premises, scope):
    """Check one line. Returns (formula or None, rule label, refs, error or None)."""
    justification = entry.justification
    parts = justification.split(None, 1) if justification is not None else []
    token = parts[0] if parts else ""
    rest = parts[1] if len(parts) > 1 else ""
    rule = _RULE_LOOKUP.get(token.lower()) if justification is not None else None

    # Always place the line, so one mistake does not wreck the scope of the lines after it.
    indent_problem = scope.enter(number, entry.depth, opens_box=rule is ASSUME)

    if justification is None:
        return None, "", [], _error(
            "BAD_LINE_SYNTAX",
            "write each line as:  formula ; rule line-numbers   (for example  Q ; ImpE 1,2)",
        )

    try:
        formula = parse(entry.formula_text)
    except FormulaError as err:
        error = err.to_dict()
        error["part"] = "formula"
        return None, token, [], error

    if rule is None:
        if not token:
            message = "write a rule after the ';', for example  ImpE 1,2"
        else:
            known = ", ".join([*RULES, ASSUME.id, *SUBPROOF_RULES])
            message = f"unknown rule {token!r}; the rules are: {known}"
        return formula, token, [], _error("UNKNOWN_RULE", message)

    if indent_problem:
        return formula, rule.id, [], _error("BAD_INDENT", indent_problem)

    items, bad = _parse_citations(rest)
    if items is None:
        return formula, rule.id, [], _error("BAD_REFERENCE", f"{bad!r} is not a line number")
    refs = _display_refs(items)

    # How many citations, and of what kind.
    if isinstance(rule, SubRule):
        if sorted(item[0] for item in items) != sorted(rule.kinds):
            return formula, rule.id, refs, _error(
                "WRONG_REFERENCE_COUNT", f"{rule.id} needs {rule.usage}"
            )
    else:
        if any(item[0] == "range" for item in items):
            return formula, rule.id, refs, _error(
                "BAD_REFERENCE", f"{rule.id} takes line numbers, not subproof ranges"
            )
        if len(items) != rule.arity:
            return formula, rule.id, refs, _error(
                "WRONG_REFERENCE_COUNT",
                f"{rule.id} needs {_plural(rule.arity, 'line number')}, but {len(items)} were given",
            )

    # Each citation must point at something earlier that this line may see.
    lines, ranges = [], []
    for item in items:
        if item[0] == "line":
            ref = item[1]
            if ref < 1 or ref >= number:
                return formula, rule.id, refs, _error(
                    "BAD_REFERENCE", f"line {ref} is not an earlier line (this is line {number})"
                )
            if parsed[ref - 1] is None:
                return formula, rule.id, refs, _error(
                    "BAD_REFERENCE", f"line {ref} has an error in its formula, so it cannot be cited"
                )
            if not scope.can_see(ref, number):
                return formula, rule.id, refs, _error(
                    "OUT_OF_SCOPE",
                    f"line {ref} is inside a subproof that has closed; "
                    "cite the whole subproof as a range (for example 2-4) instead",
                )
            lines.append(parsed[ref - 1])
        else:
            _, start, end = item
            if start < 1 or end >= number:
                bad_line = start if start < 1 else end
                return formula, rule.id, refs, _error(
                    "BAD_REFERENCE", f"line {bad_line} is not an earlier line (this is line {number})"
                )
            resolved, error = scope.resolve_range(start, end, number, parsed)
            if error is not None:
                return formula, rule.id, refs, error
            ranges.append(resolved)

    if isinstance(rule, SubRule):
        problem = rule.check(lines, ranges, formula)
    else:
        problem = rule.check(lines, formula, premises)
    if problem is not None:
        return formula, rule.id, refs, _error(*problem)
    return formula, rule.id, refs, None


def check_lines(premises, conclusion, entries) -> dict:
    """Check every line. `premises` and `conclusion` are already-parsed formulas.

    Payload: lines (one dict per line, including its nesting depth), valid (no line
    has an error), complete (valid, the last line is the conclusion, and that line is
    outside every box), in_subproof (the last line is still inside a box), error_count.
    """
    scope = _Scope()
    parsed = []
    lines = []
    for number, entry in enumerate(entries, start=1):
        formula, label, refs, error = _check_line(number, entry, parsed, premises, scope)
        parsed.append(formula)
        lines.append({
            "number": number,
            "text": entry.formula_text,
            "formula": _show(formula) if formula is not None else entry.formula_text,
            "rule": label,
            "refs": refs,
            "depth": len(scope.paths[-1]),
            "ok": error is None,
            "error": error,
        })

    error_count = sum(1 for line in lines if not line["ok"])
    valid = error_count == 0
    in_subproof = bool(scope.paths[-1])
    return {
        "lines": lines,
        "valid": valid,
        "complete": valid and not in_subproof and parsed[-1] == conclusion,
        "in_subproof": in_subproof,
        "error_count": error_count,
    }