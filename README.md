# Logic Workbench

#### Description

Logic Workbench is a web application for learning classical propositional logic. Enter a formula such as `P → (Q ∧ ¬R)` to explore its meaning, test logical relationships, transform it into normal forms, or verify a natural-deduction proof.

The application provides six tools:

- **Truth tables:** Evaluates formulas, displays their truth tables, and classifies them as tautologies, contradictions, or contingencies.
- **Equivalence:** Compares two formulas and provides a distinguishing assignment when they are not equivalent.
- **Argument validity:** Tests whether a conclusion follows from a set of premises. Invalid arguments receive a countermodel, while vacuously valid arguments are explicitly identified.
- **Normal forms:** Rewrites formulas into negation normal form (NNF), conjunctive normal form (CNF), or disjunctive normal form (DNF), showing the law applied at each step.
- **Proof checker:** Verifies natural-deduction proofs line by line, including nested subproofs, assumptions, discharged ranges, and inference rules.
- **Exercises:** Offers fifteen progressively challenging proof problems with hints, reference solutions, and anonymous attempt history.

The application is built with Flask, SQLite, HTML, CSS, JavaScript, and a pure-Python propositional-logic engine. The engine is independent of the web framework and can be tested directly.

The proof-rule conventions are based on Huth and Ryan's *Logic in Computer Science*. `IffI` and `IffE` are additional rules implemented for this project.

## Files and project structure

### Application files

- `app.py`: Defines the Flask routes, handles requests, validates input limits, calls the logic API, and renders the appropriate templates.
- `storage.py`: Implements SQLite persistence for exercise attempts, including parameterized queries and history pruning.
- `exercises.py`: Loads and structurally validates the exercise definitions.
- `exercises.json`: Contains the fifteen exercises, their premises, conclusions, hints, and reference solutions.
- `requirements.txt`: Lists the Python dependencies.
- `pytest.ini`: Configures pytest's test discovery and Python import path.
- `.gitignore`: Excludes generated files, local databases, virtual environments, and secrets.

### Logic engine (`logic/`)

The engine is deliberately separated from Flask:

- `errors.py`: Defines structured formula errors, diagnostic codes, messages, and source positions.
- `tokens.py`: Defines token types, operator aliases, and canonical symbol spellings.
- `nodes.py`: Defines the immutable abstract syntax tree (AST) and its node types.
- `lexer.py`: Tokenizes formulas and records character positions.
- `parser.py`: Implements a Pratt parser with explicit operator precedence, associativity, parenthesis handling, and nesting limits.
- `printer.py`: Produces canonical formulas while preserving AST structure, with a separate representation that makes grouping explicit.
- `evaluate.py`: Evaluates formulas under individual variable assignments.
- `truth_table.py`: Generates truth-table assignments and computes formula classifications.
- `checks.py`: Implements logical equivalence and argument-validity checks, including countermodels.
- `rewrite.py`: Implements named equivalence laws and the NNF, CNF, and DNF transformation strategies.
- `proof.py`: Implements the natural-deduction proof checker, including inference rules and subproof scope management.
- `api.py`: Provides the public interface between Flask and the engine. It converts successful results and errors into structured responses rather than exposing internal exceptions.

### Web interface

The `templates/` directory contains the Jinja templates:

- `layout.html`: Shared page structure, title block, header, and navigation.
- `index.html`: Formula input and truth-table results.
- `equivalence.html`: Formula comparison interface and distinguishing assignments.
- `argument.html`: Premise and conclusion input and validity results.
- `normal_form.html`: Normal-form selection and transformation steps.
- `proof.html`: Proof input, instructions, and verification results.
- `exercises.html`: Exercise catalogue and overall progress.
- `exercise.html`: Individual exercise, hint, proof submission, attempts, and reference solution.
- `_macros.html`: Reusable template macros, including truth-table cells.
- `_symbols.html`: Symbol palette for inserting logical operators.
- `_error.html`: Consistent presentation of formula and request errors.
- `_proof_lines.html`: Displays proof lines, scope indentation, rule references, and diagnostics.
- `_share_link.html`: Reusable copy-link control for shareable results.

The `static/` directory contains:

- `style.css`: Application styling, responsive layouts, light and dark themes, animations, and accessibility refinements.
- `app.js`: Symbol-palette interactions, formula-field targeting, and copy-link functionality.

### Tests (`tests/`)

Contains the pytest suite covering the formula language, parser and printer, evaluation, truth tables, equivalence, validity, rewriting, proof verification, Flask routes, persistence, security, and HTML rendering.

## Design decisions

**Separation of concerns.** The reasoning engine has no Flask dependencies. This keeps logical correctness independently testable and prevents web-layer concerns from leaking into the implementation of logical rules.

**Structural formulas.** Formulas are represented as immutable ASTs. Consequently, structurally different expressions remain different even when they are logically equivalent. The canonical printer preserves this grouping when its output is parsed again.

**Errors as data.** Formula and proof diagnostics include codes, messages, and source positions. Proof lines are checked independently wherever possible, allowing multiple errors to be reported without unnecessarily cascading failures.

**Explicit computational limits.** Formulas are limited to 1,000 characters and 100 levels of nesting. Computation supports up to sixteen variables, while full truth tables are displayed only for formulas with at most eight. Additional work and rewrite limits prevent pathological inputs from consuming excessive resources.

**Transparent rewriting.** Transformations apply one named law at a time. The engine intentionally does not simplify expressions, so students can inspect each logical transformation. Consequently, the resulting normal forms are not guaranteed to be minimal.

**Verification rather than proof discovery.** The proof checker verifies submitted derivations; it does not search for proofs. It supports nested subproofs and explicit range citations. The project does not claim proof-system completeness.

**Privacy.** Visitors receive an anonymous identifier stored in a signed session cookie. Only exercise attempts are persisted; formulas submitted to the other tools are not stored. CSRF protection is applied to state-changing requests, and visitors can delete their exercise history.

## Testing and limitations

The project includes 876 pytest tests. Proof-rule soundness is tested empirically by comparing accepted rule applications against truth-table semantics over a generated formula pool. This is a testing strategy, not a formal mathematical proof of soundness or completeness.

The application has several deliberate limitations: it does not search for proofs, rewriting is not minimal, and the exercise reference solutions can be revealed. These are documented design boundaries rather than hidden capabilities.

## Running the application

Install the dependencies:

    python -m pip install -r requirements.txt

Start the Flask development server:

    python -m flask --app app run

Run the tests:

    python -m pytest -q

## AI assistance

I used Claude (Anthropic) for architecture discussions, implementation, and debugging, and ChatGPT (OpenAI) for design reviews, code reviews, and interface refinements. I reviewed and tested the resulting implementation and take responsibility for the submitted work.

The relevant source files include AI-assistance comments as required by CS50x. The agents were also asked to document their own involvement. Accountability goes both ways (Not really...!).