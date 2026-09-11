# Three test layers and a 100% model coverage commit gate

The assignment grades unit tests of `model/` only. That remains the graded surface. Extra tests are in-repo so MVC seams and the scripted terminal session cannot regress without a failing command.

- **Unit** (`tests/unit`): `PIM` and Criterion. Line coverage of `model/` must be 100%, measured with stdlib `trace` (`coverage_report.py`).
- **Integration** (`tests/integration`): `controller.App` against `model.PIM` — Current Result, selection, atomic failure, save/load — without `Terminal`.
- **E2E** (`tests/e2e`): scripted stdin through `Terminal.run()`, using the existing `stdin` / `stdout` / `now` injection. No TUI library.

A versioned `hooks/pre-commit` runs unit+coverage, then integration, then e2e. Any failure blocks `git commit`. No pip: not pytest, not `coverage.py`, not the Python `pre-commit` framework. `git commit --no-verify` still exists.

100% applies to `model/` under unit tests, not to `view/` or `controller/`. TTY-only ANSI and SIGINT paths stay untested.

**Status**: accepted
