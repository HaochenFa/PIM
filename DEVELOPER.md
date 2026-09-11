# Developer manual

Platform: **macOS**. Language: **Python 3.12** (the version this tree was built with). Standard library only — do not add pip packages.

## Layout

- `model/` — Working Collection, PIR types, Search Criterion, `.pim` JSON. This is the unit-test surface.
- `view/` — designed terminal UI and in-process Alarm Alerts. Interactive TTY: stdlib `curses` (`get_wch` + 500ms timeout), `theme.py` colour roles, titled panes, `Chooser` widgets, and a calendar. Tests and redirected stdio: stdin-reader thread + 500ms `Queue.get` (typed answers, no curses).
- `controller/` — one completed user action → `model.PIM`.
- `pim.py` — composition root.
- `tests/unit/` — `model` (assignment surface, 100% lines), `controller.App`, `view.Terminal`.
- `tests/integration/` — App against PIM; Terminal against App+PIM (no stdin thread).
- `tests/e2e/` — scripted terminal sessions through `Terminal.run()`.
- `hooks/pre-commit` — refuses a commit unless unit (100% `model/` coverage), integration, and e2e all pass.

`model` must not import `view` or `controller`.

## Open and debug

Open the repository folder in any IDE (VS Code, PyCharm, or another editor). The composition root is `pim.py`.

Run:

```bash
python pim.py
```

The process uses `_curses` when both stdin and stdout are TTYs (macOS Terminal / iTerm). Colour pairs: 256-colour night-study page when `curses.COLORS >= 256`; otherwise 8-colour reverse title/selection and a red/amber alarm stamp. `TERM=dumb` or a missing `_curses` falls back to the line UI.

To force the line UI:

```bash
PIM_NO_CURSES=1 python pim.py
```

Unit, integration, and e2e tests inject non-TTY streams, so they never enter the curses loop. Do not drive `curses.initscr` from `unittest`.

Debug:

```bash
python -m pdb pim.py
```

Or use the IDE debugger: set the launch target to `pim.py` in this folder (Python 3.12). No build step; there is nothing to compile.

## Test

All layers:

```bash
python -m unittest
```

By layer:

```bash
python -m unittest discover -s tests/unit -t .
python -m unittest discover -s tests/integration -t .
python -m unittest discover -s tests/e2e -t .
```

## Line coverage (`model/`)

```bash
python coverage_report.py
```

Writes `coverage.txt` at the source root. Uses `trace` from the standard library on `tests/unit` only. Exit status is 1 unless every countable line in `model/` was hit.

## Pre-commit hook

Once per clone:

```bash
git config core.hooksPath hooks
```

`git commit` then runs unit tests + 100% `model/` coverage, then integration, then e2e. Bypass with `git commit --no-verify`. No pip packages.

## Product decisions

Do not reopen locked decisions. Read `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/ACCEPTANCE.md`, `CONTEXT.md`, `docs/adr/`, and `AGENTS.md`.
