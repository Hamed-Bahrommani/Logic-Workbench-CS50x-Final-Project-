"""Logic Workbench web app: a thin Flask layer over the pure-Python engine.

This file knows about HTTP and HTML. It knows nothing about logic: every
answer comes from logic.api, which never raises and always returns a dict.
"""


from flask import Flask, render_template, request

from logic import api

from logic.proof import ALL_RULES

app = Flask(__name__)

# The engine caps variables and nesting; these cap the raw size of what a
# visitor can send, before any parsing happens.
MAX_INPUT_LENGTH = 1000                       # one formula
MAX_PREMISES_TEXT = 20 * MAX_INPUT_LENGTH     # the whole list of premises

EXAMPLES = [
    "P → (Q ∧ ¬R)",
    "P ∨ ¬P",
    "¬(P ∧ Q) ↔ ¬P ∨ ¬Q",
    "((P → Q) → P) → P",
]

CLASSIFICATION_HELP = {
    "tautology": "true under every assignment",
    "contradiction": "false under every assignment",
    "contingency": "true under some assignments and false under others",
}

EQUIVALENCE_EXAMPLES = [
    {"left": "P → Q", "right": "¬P ∨ Q"},
    {"left": "¬(P ∧ Q)", "right": "¬P ∨ ¬Q"},
    {"left": "P → (Q → R)", "right": "(P ∧ Q) → R"},
    {"left": "P → Q", "right": "Q → P"},
]

NORMAL_FORMS = {
    "nnf": "Negation normal form (NNF)",
    "cnf": "Conjunctive normal form (CNF)",
    "dnf": "Disjunctive normal form (DNF)",
}

NORMAL_FORM_EXAMPLES = [
    {"formula": "P → (Q ∧ R)", "strategy": "cnf"},
    {"formula": "¬(P → Q)", "strategy": "nnf"},
    {"formula": "(P ∨ Q) ∧ (R ∨ S)", "strategy": "dnf"},
    {"formula": "P ↔ Q", "strategy": "cnf"},
]


def _argument_example(premises: list[str], conclusion: str) -> dict:
    return {
        "premises": "\n".join(premises),
        "conclusion": conclusion,
        "label": ", ".join(premises) + " ∴ " + conclusion,
    }


ARGUMENT_EXAMPLES = [
    _argument_example(["P → Q", "P"], "Q"),
    _argument_example(["P → Q", "Q"], "P"),
    _argument_example(["P ∨ Q", "¬P"], "Q"),
    _argument_example(["P ∧ ¬P"], "Q"),
]

FIELD_LABELS = {"left": "First formula", "right": "Second formula", "conclusion": "Conclusion"}



MAX_PROOF_TEXT = 100 * MAX_INPUT_LENGTH

PROOF_EXAMPLES = [
    {
        "label": "Modus ponens",
        "premises": "P → Q\nP",
        "conclusion": "Q",
        "proof": "P → Q ; premise\nP ; premise\nQ ; ImpE 1,2",
    },
    {
        "label": "Swap a conjunction",
        "premises": "P ∧ Q",
        "conclusion": "Q ∧ P",
        "proof": "P ∧ Q ; premise\nP ; AndE 1\nQ ; AndE 1\nQ ∧ P ; AndI 3,2",
    },
    {
        "label": "Anything follows from a contradiction",
        "premises": "P\n¬P",
        "conclusion": "Q",
        "proof": "P ; premise\n¬P ; premise\n⊥ ; NotE 1,2\nQ ; BotE 3",
    },
    {
        "label": "Chain two implications",
        "premises": "P → Q\nQ → R\nP",
        "conclusion": "R",
        "proof": "P → Q ; premise\nQ → R ; premise\nP ; premise\nQ ; ImpE 1,3\nR ; ImpE 2,4",
    },
]

PROOF_EXAMPLES += [
    {
        "label": "P implies P (a subproof)",
        "premises": "",
        "conclusion": "P → P",
        "proof": "| P ; assume\nP → P ; ImpI 1-1",
    },
    {
        "label": "Contraposition (nested subproofs)",
        "premises": "P → Q",
        "conclusion": "¬Q → ¬P",
        "proof": "\n".join([
            "P → Q ; premise",
            "| ¬Q ; assume",
            "| | P ; assume",
            "| | Q ; ImpE 1,3",
            "| | ⊥ ; NotE 4,2",
            "| ¬P ; NotI 3-5",
            "¬Q → ¬P ; ImpI 2-6",
        ]),
    },
    {
        "label": "Disjunction commutes (proof by cases)",
        "premises": "P ∨ Q",
        "conclusion": "Q ∨ P",
        "proof": "\n".join([
            "P ∨ Q ; premise",
            "| P ; assume",
            "| Q ∨ P ; OrI 2",
            "| Q ; assume",
            "| Q ∨ P ; OrI 4",
            "Q ∨ P ; OrE 1,2-3,4-5",
        ]),
    },
]


@app.get("/")
def index():
    """Show the form; if a formula was submitted, show its truth table too.

    The formula travels in the query string (GET, not POST) because computing a
    table changes nothing on the server. That makes every result a link that can
    be bookmarked or shared, and the Back button works.
    """
    submitted = "formula" in request.args
    text = request.args.get("formula", "")

    result = None
    error_context = None
    if submitted:
        result = _length_error(text, "formula") or api.truth_table(text)
        if not result["ok"]:
            error_context = _error_context(text, result["error"].get("position"))

    return render_template(
        "index.html",
        text=text,
        result=result,
        error_context=error_context,
        examples=EXAMPLES,
        classification_help=CLASSIFICATION_HELP,
    )


@app.get("/equivalence")
def equivalence():
    """Are two formulas equivalent? If not, show the first assignment that tells them apart."""
    submitted = "left" in request.args or "right" in request.args
    left = request.args.get("left", "")
    right = request.args.get("right", "")

    result = None
    error_context = None
    error_label = None
    if submitted:
        result = (
            _length_error(left, "formula", "left")
            or _length_error(right, "formula", "right")
            or api.equivalent(left, right)
        )
        if not result["ok"]:
            error_context, error_label = _field_error(
                result["error"], {"left": left, "right": right}
            )

    return render_template(
        "equivalence.html",
        left=left,
        right=right,
        result=result,
        error_context=error_context,
        error_label=error_label,
        examples=EQUIVALENCE_EXAMPLES,
    )


@app.get("/argument")
def argument():
    """Is an argument valid? If not, show a countermodel."""
    submitted = "premises" in request.args or "conclusion" in request.args
    premises_text = request.args.get("premises", "")
    conclusion = request.args.get("conclusion", "")
    # Blank lines are ignored, so premise numbers count only the non-blank lines.
    premises = _premise_lines(premises_text) if len(premises_text) <= MAX_PREMISES_TEXT else []

    result = None
    error_context = None
    error_label = None
    if submitted:
        result = _check_argument(premises_text, premises, conclusion)
        if not result["ok"]:
            fields = {f"premise-{number}": line for number, line in enumerate(premises, start=1)}
            fields["conclusion"] = conclusion
            error_context, error_label = _field_error(result["error"], fields)

    return render_template(
        "argument.html",
        premises_text=premises_text,
        conclusion=conclusion,
        result=result,
        error_context=error_context,
        error_label=error_label,
        examples=ARGUMENT_EXAMPLES,
    )


@app.get("/normal-form")
def normal_form():
    """Rewrite a formula into NNF, CNF or DNF, showing every law applied."""
    submitted = "formula" in request.args
    text = request.args.get("formula", "")
    strategy = request.args.get("strategy", "cnf")

    result = None
    error_context = None
    if submitted:
        result = _length_error(text, "formula") or api.normal_form(text, strategy)
        if not result["ok"]:
            error_context = _error_context(text, result["error"].get("position"))

    return render_template(
        "normal_form.html",
        text=text,
        strategy=strategy,
        strategies=NORMAL_FORMS,
        result=result,
        error_context=error_context,
        error_label=None,
        examples=NORMAL_FORM_EXAMPLES,
    )


@app.get("/proof")
def proof_checker():
    """Check a natural-deduction proof, line by line."""
    submitted = any(key in request.args for key in ("premises", "conclusion", "proof"))
    premises_text = request.args.get("premises", "")
    conclusion = request.args.get("conclusion", "")
    proof_text = request.args.get("proof", "")
    premises = _premise_lines(premises_text) if len(premises_text) <= MAX_PREMISES_TEXT else []

    result = None
    error_context = None
    error_label = None
    if submitted:
        result = _check_proof_request(premises_text, premises, conclusion, proof_text)
        if not result["ok"]:
            fields = {f"premise-{number}": line for number, line in enumerate(premises, start=1)}
            fields["conclusion"] = conclusion
            error_context, error_label = _field_error(result["error"], fields)

    return render_template(
        "proof.html",
        premises_text=premises_text,
        conclusion=conclusion,
        proof_text=proof_text,
        result=result,
        error_context=error_context,
        error_label=error_label,
        examples=PROOF_EXAMPLES,
        rules=ALL_RULES,
    )


def _check_proof_request(premises_text, premises, conclusion, proof_text) -> dict:
    too_long = _length_error(premises_text, "list of premises", limit=MAX_PREMISES_TEXT)
    if too_long:
        return too_long
    for number, line in enumerate(premises, start=1):
        too_long = _length_error(line, "premise", f"premise-{number}")
        if too_long:
            return too_long
    return (
        _length_error(conclusion, "conclusion", "conclusion")
        or _length_error(proof_text, "proof", limit=MAX_PROOF_TEXT)
        or api.check_proof(premises, conclusion, proof_text)
    )

def _premise_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _check_argument(premises_text: str, premises: list[str], conclusion: str) -> dict:
    too_long = _length_error(premises_text, "list of premises", limit=MAX_PREMISES_TEXT)
    if too_long:
        return too_long
    for number, line in enumerate(premises, start=1):
        too_long = _length_error(line, "premise", f"premise-{number}")
        if too_long:
            return too_long
    return _length_error(conclusion, "conclusion", "conclusion") or api.valid(premises, conclusion)


def _length_error(
    text: str, what: str, field: str | None = None, limit: int = MAX_INPUT_LENGTH
) -> dict | None:
    """An error result if `text` is over `limit` characters, otherwise None."""
    if len(text) <= limit:
        return None
    error = {
        "code": "INPUT_TOO_LONG",
        "message": f"The {what} is too long ({len(text)} characters; the limit is {limit}).",
    }
    if field is not None:
        error["field"] = field
    return {"ok": False, "error": error}


def _field_label(field: str | None) -> str | None:
    if field is None:
        return None
    if field.startswith("premise-"):
        return "Premise " + field.removeprefix("premise-")
    return FIELD_LABELS.get(field, field)


def _field_error(error: dict, fields: dict[str, str]) -> tuple[dict | None, str | None]:
    """The caret display and the label for an error that may name one of several inputs."""
    field = error.get("field")
    text = fields.get(field) if field is not None else None
    context = _error_context(text, error.get("position")) if text is not None else None
    return context, _field_label(field)


def _error_context(text: str, position: int | None) -> dict | None:
    """The input line plus a caret line pointing at the error, for a <pre> block.

    Tabs and newlines become spaces so that the caret lines up with the
    character index the engine reported.
    """
    if position is None or len(text) > MAX_INPUT_LENGTH:
        return None
    line = "".join(" " if ch in "\t\r\n" else ch for ch in text)
    return {"line": line, "caret": " " * position + "^"}