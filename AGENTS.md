# Agent instructions

Standing rules for human and agent contributors. The architecture and accepted decisions are in [docs/SPEC.md](docs/SPEC.md); open work is tracked in [docs/TODO.md](docs/TODO.md); safeguards learned from mistakes are in [docs/lessons.md](docs/lessons.md).

## Authority and workflow

- Never work on `main`. Pushing, merging, deleting branches, tagging releases and publishing require explicit permission in the current request.
- `docs/SPEC.md` is the source of truth. Interview the user before implementing new or complex features, and distinguish proposals from accepted decisions.
- Review `docs/lessons.md` at session start; record each new mistake there with its date and rationale.
- Review three to five comparable files before writing new code; for nontrivial changes, consider whether a simpler design meets the requirement.
- Validate at small scale before full runs. Measure performance; never invent benchmark results.
- Create local commits after verified milestones.

## Confidentiality

- This repository is **public**. It must never contain MUST project content: no MUST requirement records, subsystem codes, names, schedules, documents or values. The MUST record lives in the private repository `MUST-Science-Collaboration/must_req`.
- Examples, fixtures and documentation use the fictional project DEMO only.

## Code

- English for code, documentation, commits and logs.
- `snake_case` for identifiers and file names, with specific, complete words; never camelCase. No comments that merely repeat a name.
- `uv` only for environments and dependencies (never pip, Poetry or Conda). Ruff, run through pre-commit, is the single source of truth for lint and format.
- Python 3.11–3.14. Package code lives in `src/qingsong/`.

## Tests

- Tests build synthetic vaults in temporary directories. They never read or write a real vault, never change the working directory globally, and never set environment variables outside a test's own scope.
- Pass a fixed `today` to every operation a test calls. A test that mixes a fixed date with the real date fails on another day.
- Every check rule has a fixture that triggers it. Failures are never masked in CI.

## Documentation

- The Markdown files are the sources: `README.md`, `AGENTS.md` and `docs/*.md`. Never edit the HTML in `docs/html/` or `docs/index.html`, or the generated part of `docs/api.md`.
- After changing a document, a docstring, a command or a check rule, run `uv run python tools/build_docs.py` and commit the result. `tests/test_docs.py` fails while anything generated is out of date.
- Keep `docs/howto.md` true: run every example in it on a copy of the demo vault after changing a command it shows.
