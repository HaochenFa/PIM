# Three test layers and a 100% model coverage commit gate

The assignment grades unit tests of `model/` only. That remains the graded surface. Extra tests are in-repo so MVC seams and the scripted terminal session cannot regress without a failing command.

- **Unit** (`tests/unit`): `PIM` and Criterion (graded; `model/` line coverage 100% via stdlib `trace`); `controller.App` with a mocked PIM; `view.Terminal` with a fake App.
- **Integration** (`tests/integration`): `controller.App` against `model.PIM`; `view.Terminal` against App+PIM on one thread (no stdin reader).
- **E2E** (`tests/e2e`): scripted stdin through `Terminal.run()`, using the existing `stdin` / `stdout` / `now` injection. No TUI library.

A versioned `hooks/pre-commit` runs unit+coverage, then integration, then e2e. Any failure blocks `git commit`. No pip: not pytest, not `coverage.py`, not the Python `pre-commit` framework. `git commit --no-verify` still exists.

100% applies to `model/` under unit tests, not to `view/` or `controller/`. TTY-only ANSI and SIGINT paths stay untested.

**Status**: accepted
