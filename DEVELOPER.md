# Developer manual

Platform: **macOS**. Language: **Python 3.12** (the version this tree was built with). Standard library only — do not add pip packages.

## Layout

- `model/` — Working Collection, PIR types, Search Criterion, `.pim` JSON. This is the unit-test surface.
- `view/` — designed terminal UI and in-process Alarm Alerts (stdin thread + 500ms tick).
- `controller/` — one completed user action → `model.PIM`.
- `pim.py` — composition root.
- `tests/` — `unittest` for `model` only.

`model` must not import `view` or `controller`.

## Run

```bash
python pim.py
```

## Test

```bash
python -m unittest
```

## Line coverage (`model/`)

```bash
python coverage_report.py
```

Writes `coverage.txt` at the source root. Uses `trace` from the standard library.

## Product decisions

Do not reopen locked decisions. Read `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/ACCEPTANCE.md`, `CONTEXT.md`, `docs/adr/`, and `AGENTS.md`.
