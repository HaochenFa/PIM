# Developer manual

Platform: **macOS only** (developed on macOS with Python 3.12.9). Language: **Python 3.12** or newer. Standard library only — do not add pip packages. There is no build step and nothing to compile.

`model` reads the time zone `Asia/Hong_Kong` from the system time-zone database through `zoneinfo`, which macOS provides. Other platforms are not supported: for example, Windows has no system database without the third-party `tzdata` package.

Use `python3` in every command below. Stock macOS has no `python` command.

## Layout

- `model/` — Working Collection, PIR types, Search Criterion, `.pim` JSON. This is the unit-test surface.
- `view/` — designed terminal UI and in-process Alarm Alerts. Interactive TTY: stdlib `curses` (`get_wch` + 500ms timeout), `theme.py` colour roles, titled panes, `Chooser` widgets, a calendar, and a folder browser for load / save-as paths. Tests and redirected stdio: stdin-reader thread + 500ms `Queue.get` (typed answers, no curses).
- `controller/` — one completed user action → `model.PIM`.
- `pim.py` — composition root.
- `tests/unit/` — `model` (assignment surface, 100% lines), `controller.App`, `view.Terminal`.
- `tests/integration/` — App against PIM; Terminal against App+PIM (no stdin thread).
- `tests/e2e/` — scripted terminal sessions through `Terminal.run()`.
- `hooks/pre-commit` — refuses a commit unless unit (100% `model/` coverage), integration, and e2e all pass.

`model` must not import `view` or `controller`.

## Open and debug

IDE: **Visual Studio Code** with Microsoft's **Python** extension (`ms-python.python`). Open the repository folder (*File → Open Folder…*), then pick the Python 3.12 interpreter (*Python: Select Interpreter*). The composition root is `pim.py`.

Run from a terminal at the repository root:

```bash
python3 pim.py
```

The process uses `_curses` when both stdin and stdout are TTYs (macOS Terminal / iTerm, or the VS Code integrated terminal). Colour pairs: 256-colour night-study page when `curses.COLORS >= 256`; otherwise 8-colour reverse title/selection and a red/amber alarm stamp. `TERM=dumb` or a missing `_curses` falls back to the line UI.

To force the line UI:

```bash
PIM_NO_CURSES=1 python3 pim.py
```

Unit, integration, and e2e tests inject non-TTY streams, so they never enter the curses loop. Do not drive `curses.initscr` from `unittest`.

### Debug mode

In VS Code: open `pim.py`, then *Run and Debug → Python Debugger: Debug Python File*. The debugger runs the program in the integrated terminal, which is a TTY, so the curses screen appears there. Breakpoints in `model/`, `controller/`, or `view/` stop as usual. To step through without the curses screen, add `"env": {"PIM_NO_CURSES": "1"}` to the launch configuration.

From a terminal, with the standard-library debugger:

```bash
python3 -m pdb pim.py
```

## Test

All layers:

```bash
python3 -m unittest
```

By layer:

```bash
python3 -m unittest discover -s tests/unit -t .
python3 -m unittest discover -s tests/integration -t .
python3 -m unittest discover -s tests/e2e -t .
```

## Line coverage (`model/`)

```bash
python3 coverage_report.py
```

Writes `coverage.txt` at the source root. Uses `trace` from the standard library on `tests/unit` only. A line counts if an AST statement starts on it; docstrings, comments, and continuation lines are not counted, and `model/__init__.py` (re-exports only) is excluded. Exit status is 1 unless every countable line in `model/` was hit. Totals can differ slightly from third-party `coverage.py`, which this project does not use.

## Pre-commit hook

Once per clone:

```bash
git config core.hooksPath hooks
```

`git commit` then runs unit tests + 100% `model/` coverage, then integration, then e2e. Bypass with `git commit --no-verify`. No pip packages.

## Product decisions

Do not reopen locked decisions. Read the SRS (`docs/deliverables/SRS.md`), the design document and its decisions (`docs/deliverables/DESIGN.md`, §5), and `AGENTS.md`. Open work is listed in `docs/BACKLOG.md`.
