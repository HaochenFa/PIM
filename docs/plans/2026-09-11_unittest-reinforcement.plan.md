# Integration / e2e tests and pre-commit gate

## Context

The brief grades **model unit tests**. Extra test layers are allowed because this request is explicit (`AGENTS.md`: test `model` only unless asked for more).

Constraints that stay locked:

- `unittest` + standard library only (no pytest, no `coverage.py`, no Python `pre-commit` package)
- `model` stays a deep module: no threads, stdin, or ANSI
- View already injects `stdin` / `stdout` / `now` — e2e must use that seam, not a TUI library
- Failed commands remain atomic; tests assert no mutation plus one English status

Current state: `tests/test_*.py` cover `model` only. `coverage.txt` reports **~80%** of `model/` (`trace` + `coverage_report.py`). `.git/hooks/` has samples only.

## Test layout

Keep shared fixture at `tests/fixture.py`. Split suites so the hook can run them separately:

```
tests/
  fixture.py                 # ACCEPTANCE §4 fixture (unchanged)
  unit/
    test_pim.py test_pir.py test_search.py test_persist.py test_alarms.py
    test_app.py test_errors.py          # controller
    test_terminal.py test_stdin_reader.py
  integration/
    test_app.py              # App ↔ PIM
    test_terminal.py         # Terminal ↔ App ↔ PIM, no stdin thread
  e2e/
    harness.py
    test_user_flows.py test_demo.py test_alerts.py test_commands.py
```

`python -m unittest` from the source root still discovers **all three** layers (nested `test_*.py`). Coverage tracing uses **unit only**.

Move, do not duplicate, the existing model tests. Update imports only if needed (`from tests.fixture import make_fixture` still works).

## Layer 1 — Unit (`model/`, 100% line coverage)

**Job:** assignment surface + the 100% gate.

`coverage_report.py` changes:

- Discover `tests/unit` only (e2e/integration must not inflate model coverage)
- Skip multi-line docstrings (today they are counted as executable and can never hit 100%)
- Exit **1** if tests fail **or** `model/` total is not 100.0%
- Keep writing `coverage.txt` at the source root (assignment artefact)
- Add `--check` for the hook: same rules, write the report only when coverage is 100% so a failing commit does not dirty the tree

Fill real gaps with more `unittest` cases (stdlib `unittest.mock` where an `OSError` path cannot be reached with a temp file):

- Criterion parser: `()`, `!!`, unknown type/field/op, missing-field `contains`/`deadline`, escaped / unterminated strings, space-separated datetimes, unexpected tokens
- PIR helpers: `parse_datetime` (`Z`, naive object, `none`), `parse_optional_datetime`, `parse_alarm` from JSON, relative unit aliases (`days`), `display_field`, `pir_from_json` bad schema, Contact `none` clears optional fields
- Persistence: `next_id <= 0`, `pirs` not a list, atomic-write failure (`os.replace` raises; temp unlinked)
- Abstract `NotImplementedError` on `Criterion.matches` / `PIR` hooks

Do **not** require 100% of `view/` or `controller/`. Unit coverage means `model/` lines under unit tests, matching the brief.

## Layer 2 — Integration (`controller.App` + `model.PIM`)

**Job:** module seams, not keystrokes. Construct `App(PIM())` (or `App(make_fixture())`) and call App methods.

Must assert:

| Seam | Expected |
|---|---|
| `create` four types | selection + Current Result + status `Created … Id n` |
| failed create (blank required field, unknown type) | status set; collection unchanged; not dirty |
| `search` / `clear_search` | Current Result is hits, then the whole collection |
| illegal criterion | status is the syntax error; Current Result **unchanged** |
| `select_row` / `select_id` | row is 1-based and not identity; bad row / unknown Id fail |
| `print_selected` / `print_all` | `print all` is Current Result, not `pim.all()` after a search |
| `modify` / `delete_selected` | Id stable; empty fields → `No changes` and not dirty; no selection fails |
| `save` / `save as` / `load` | `.pim` appended; non-`.pim` rejected; dirty load without `force` fails; `force=True` discards; corrupt file does not clobber |
| `would_overwrite` / `save_target` | overwrite only for a different existing path |
| selection after search | PIR that leaves the hit list is unselected |
| `message_for` | `PIMError` → `status_message()`; `OSError` → `str`; other → `command failed` |

No `Terminal`, no threads, no ANSI.

## Layer 3 — E2E (simulated user)

**Job:** one completed session through `Terminal.run()`, as a user types.

Harness (`tests/e2e/harness.py`):

- File-like stdin: a list of lines, then EOF; `isatty()` is False
- `io.StringIO` stdout
- `PIM()` → `App(pim)` → `Terminal(app, stdin=…, stdout=…, now=…)` → `run()`
- Last line is `quit` (or `discard` then `quit` when dirty)
- Inject `now` for alarms (View already supports this)
- Assert on `app` state (Current Result Ids, selection, dirty, bound path) **and** on captured screen text (status line, DETAIL, ALARMS banner, PRINT)

This is real e2e of the event loop + stdin-reader thread without a 0.5s wait per command: preload every line, then `run()`.

Scripts (each test names the behaviour):

1. **Demo** — ACCEPTANCE §6: empty start → create Note / Task (no deadline) / Event (two relative + one absolute) / Contact → `search type = event && description contains "COMP"` → select → change start → Relative times move, Absolute stays → `print` → `save as` temp `.pim` → quit → new process `load` → Id still there
2. **Create/validate** — four wizards; whitespace-only required field fails; collection unchanged
3. **Modify** — empty enter keeps values; no selection → fail
4. **Search** — fixture criteria from ACCEPTANCE §4; syntax error leaves the list
5. **Print** — `print` with no selection fails; `print all` after search is hits only
6. **Delete** — `n` unchanged; `y` removes Id; next create Id ≥ 7, never reused
7. **Store/load** — `save as` without suffix writes `.pim`; `load` of `.json` fails; dirty quit/load offers save / discard / cancel; cancel leaves state
8. **Alarms** — inject `now` in OVERDUE and SOON windows; banner appears on first paint after create; `dismiss` drops that `(Id, index)` in this process only; `.pim` has no dismiss data
9. **Unknown command** — status `unknown command: …`; no mutation

Do not test TTY-only ANSI / SIGINT paths. Those are not user-story operations.

## Pre-commit hook

Versioned at `hooks/pre-commit` (POSIX `sh`, macOS). **No pip.**

On every `git commit`:

1. `python3 coverage_report.py --check` — unit tests + **100%** `model/` lines
2. `python3 -m unittest discover -s tests/integration -t .`
3. `python3 -m unittest discover -s tests/e2e -t .`

Any non-zero exit **blocks the commit**. Print which layer failed.

Install (course platform is macOS):

- Document in `DEVELOPER.md`: `git config core.hooksPath hooks`
- Also copy/install into `.git/hooks/pre-commit` in this clone so the gate is on immediately
- `git commit --no-verify` still exists; do not try to disable it

Do not add a `Makefile` or a third-party hook runner.

## Docs (no product rewrite)

User-facing product/architecture/acceptance stay locked. Additive developer docs only:

- **ADR 0017** — three test layers; 100% model line coverage as a commit gate; stdlib `trace`; why extra tests are outside the graded surface but in-repo
- **`AGENTS.md` testing rules** — unit = `model`; integration = App+PIM; e2e = Terminal scripts; pre-commit requires all three + 100%
- **`DEVELOPER.md` / `README.md`** — commands for each suite, coverage, hook install
- **`docs/ARCHITECTURE.md` package tree** — one-line update of `tests/` so it is not still “model only” (layout, not a product decision)

Do not change `docs/PRODUCT.md` or `docs/ACCEPTANCE.md`.

## Commits (split)

Each commit leaves `python -m unittest` green:

1. `test(model): close unit gaps and require 100% model coverage`
2. `test(controller): add App–PIM integration tests`
3. `test(view): add scripted-terminal e2e tests`
4. `chore(hooks): block commit unless unit, integration, and e2e pass`
5. `docs: record three test layers and the pre-commit gate`

## Out of scope

- GUI / curses / colour / third-party test runners
- 100% line coverage of `view/` or `controller/`
- OS notifications, daemons, recurrence, PIR links
- Changing PIR type, fuzzy search, extra commands

## How to check (after implementation)

```bash
python -m unittest
python coverage_report.py          # TOTAL model/ 100.0%; coverage.txt at source root
python -m unittest discover -s tests/unit -t .
python -m unittest discover -s tests/integration -t .
python -m unittest discover -s tests/e2e -t .
git config core.hooksPath hooks    # then a commit is refused if any layer fails
```
