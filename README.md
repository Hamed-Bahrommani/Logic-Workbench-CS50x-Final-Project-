# Logic Workbench

#### Video Demo: <PASTE YOUR VIDEO URL HERE>

#### Description:

Logic Workbench is a web application for learning classical propositional logic. You type a formula, such as `P → (Q ∧ ¬R)`, and the site shows you what it means and lets you test your reasoning against it. It has six tools:

- **Truth table:** classifies a formula as a tautology, a contradiction or a contingency.
- **Equivalence:** decides whether two formulas are equivalent and, if not, shows the first assignment that tells them apart.
- **Argument validity:** decides whether premises entail a conclusion and, if not, shows a countermodel. It flags arguments that are valid only because the premises contradict each other.
- **Normal forms:** rewrites a formula into NNF, CNF or DNF one step at a time, naming the law used at each step.
- **Proof checker:** checks a natural-deduction proof line by line, including nested subproofs.
- **Exercises:** fifteen graded proof problems, with hints, stored solutions and an anonymous attempt history.

The project is built with Flask, SQLite and pure Python. The reasoning engine is tested without a web server. The rule set follows Huth & Ryan, *Logic in Computer Science* (<EDITION>), with `IffI` and `IffE` added as derived rules.

## Files

- `app.py`: the Flask routes. It validates sizes, calls the engine, and renders templates. It contains no logic of its own.
- `storage.py`: the SQLite layer for exercise attempts. Every query is parameterised, and old attempts are pruned.
- `exercises.py` and `exercises.json`: the exercise data and its loader. The loader checks structure; the tests check that every exercise is a valid argument with a working stored solution.
- `logic/`: the engine, importable on its own.
  - `errors.py`, `tokens.py`, `nodes.py`: error types, token kinds and the immutable syntax tree.
  - `lexer.py`, `parser.py`: a hand-written lexer and a Pratt parser with precedence and associativity rules, ASCII aliases for every symbol, and a nesting limit.
  - `printer.py`: prints a tree with minimal parentheses, or with explicit grouping for readability.
  - `evaluate.py`, `truth_table.py`, `checks.py`: evaluation, truth tables, equivalence and validity.
  - `rewrite.py`: the named laws and the NNF, CNF and DNF strategies.
  - `proof.py`: the proof checker.
  - `api.py`: the only module the web layer talks to. It never raises; it returns `{"ok": True, ...}` or `{"ok": False, "error": ...}`.
- `templates/` and `static/`: Jinja templates and one stylesheet, with dark mode and a small script that adds a symbol palette.
- `tests/`: over 870 pytest tests.

## Design decisions

**The engine is separate from the web layer.** Every rule of logic lives in `logic/` and is tested directly. The Flask layer only translates between forms and results. That is why the tests run in about ten seconds.

**Errors are data.** The engine returns errors with a code, a message and a position, and the page draws a caret under the mistake. Proof lines are judged independently, so one run reports every error, and a mistake on one line does not cascade into the lines after it.

**Limits are explicit.** Formulas are capped at 1,000 characters, 100 levels of nesting, and 16 variables. Truth tables are shown for up to 8. Rewrites stop at 200 nodes, because the CNF of some formulas grows exponentially. Hitting a limit gives a clear error, never a hang.

**Rewriting never simplifies.** Each step applies one named law at one place, in a fixed order. A student can check every step by hand. The cost is that results are not minimal, which the tool does not hide.

**The proof checker verifies and never searches.** Scope follows the textbook: a line can cite earlier lines in its own subproof or an enclosing one, and a closed subproof only as a whole range such as `ImpI 3-5`.

**Anonymous by design.** A visitor is a random id in a signed cookie. Only exercise attempts are stored, never the formulas typed into the other tools. A "Forget my history" button deletes everything. POSTs carry a CSRF token. Read-only tools use GET so results are shareable links.

## Testing

`pytest` runs the whole suite. Soundness of the proof checker is tested by brute force: every accepted rule application over a pool of formulas is checked against the truth-table validator, and every rule must have at least one accepted case. I claim soundness only for what is tested, and I do not claim the checker finds proofs.

## Running it

    pip install -r requirements.txt
    flask --app app run
    pytest

## AI assistance

I built this project together with Claude (Anthropic) and reviewed designs with ChatGPT (OpenAI). Files carry a comment saying so.