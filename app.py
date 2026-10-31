"""Logic Workbench web app: a thin Flask layer over the pure-Python engine.

This file knows about HTTP and HTML. It knows nothing about logic: every
answer comes from logic.api, which never raises and always returns a dict.
"""


from flask import Flask, render_template, request

from logic import api

app = Flask(__name__)

# The engine caps variables and nesting; this caps the raw size of what a
# visitor can send, before any parsing happens.
MAX_INPUT_LENGTH = 1000

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
        result = _compute(text)
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


def _compute(text: str) -> dict:
    if len(text) > MAX_INPUT_LENGTH:
        return {
            "ok": False,
            "error": {
                "code": "INPUT_TOO_LONG",
                "message": f"The formula is too long ({len(text)} characters; "
                           f"the limit is {MAX_INPUT_LENGTH}).",
            },
        }
    return api.truth_table(text)


def _error_context(text: str, position: int | None) -> dict | None:
    """The input line plus a caret line pointing at the error, for a <pre> block.

    Tabs and newlines become spaces so that the caret lines up with the
    character index the engine reported.
    """
    if position is None or len(text) > MAX_INPUT_LENGTH:
        return None
    line = "".join(" " if ch in "\t\r\n" else ch for ch in text)
    return {"line": line, "caret": " " * position + "^"}