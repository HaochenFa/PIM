# COMP3211 PIM

Command-line Personal Information Management system for PolyU COMP3211 Software Engineering (Fall 2026).

The assignment brief is [`Project Description.pdf`](Project Description.pdf). Product decisions, architecture, and acceptance criteria are locked in the documents below. Implementation must follow those files, not reopen them.

## Documents

| File | What it is |
|---|---|
| [`docs/PRODUCT.md`](docs/PRODUCT.md) | Product scope, PIR types, search, persistence, interaction |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | MVC, `model` interface, event loop, `.pim` JSON, search-then-update sequence |
| [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) | Observable criteria for US1–US11, tests, ZIP contents, demo script |
| [`CONTEXT.md`](CONTEXT.md) | Domain glossary (PIR, Id, Alarm, Current Result, …) |
| [`docs/deliverables/SRS.md`](docs/deliverables/SRS.md) | Software requirements specification (course deliverable 1) |
| [`docs/deliverables/DESIGN.md`](docs/deliverables/DESIGN.md) | Design document (deliverable 2); §5 records the design decisions and their reasons |
| [`docs/BACKLOG.md`](docs/BACKLOG.md) | Open deliverables, manual checks, known UI gaps, and a log of what landed |
| [`AGENTS.md`](AGENTS.md) | Rules for AI agents: precedence, scope, architecture, gates |

Use the glossary terms as written. Do not treat **Name** as a title, **Label** as identity, or **Note** as a field name.

## Product in one paragraph

A single-user terminal PIM. The user manages Notes, Tasks, Events, and Contacts in a Working Collection, searches with contains / time comparison / `&&` `||` `!`, and stores the collection in a UTF-8 JSON file with the extension `.pim`. Python 3 and the standard library only. No GUI, no third-party TUI, no recurrence, no network.

## Layout

```
model/          # required package name; the unit-test surface
view/           # designed terminal UI and in-process Alarm Alerts
controller/     # one user action → model.PIM
pim.py          # composition root: python3 pim.py
tests/unit/     # model (100% lines) + controller + view
tests/integration/
tests/e2e/
hooks/          # pre-commit: unit + integration + e2e
docs/
CONTEXT.md
README.md
```

Run with `python3 pim.py`. Tests: `python3 -m unittest`. Coverage: `python3 coverage_report.py` (must be 100% of `model/`). Enable the commit gate: `git config core.hooksPath hooks`. See [`DEVELOPER.md`](DEVELOPER.md) and [`USER.md`](USER.md). Story coverage: [`REQUIREMENTS.md`](REQUIREMENTS.md).

## Constraints that affect every commit

- Importable top-level package named `model`
- Standard library only (no pip dependencies)
- Default timezone: Hong Kong Time (`Asia/Hong_Kong`)
- Failed commands do not mutate data, dump a traceback, or exit
- Unit tests target `model/` with `unittest` at 100% line coverage; integration and e2e suites also run under `unittest`; line-coverage report at the source root

## Submission

One ZIP by **20:00, 20 November 2026**: SRS, design document, source, manuals, ≤4 min system video, requirements coverage table, model tests and coverage report, presentation PDF and ≤5 min recording, Honour Declaration at the ZIP root.

Checklist and demo script: [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md).
