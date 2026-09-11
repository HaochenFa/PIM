# COMP3211 PIM

Command-line Personal Information Management system for PolyU COMP3211 Software Engineering (Fall 2026).

The assignment brief is [`Project Description.pdf`](Project Description.pdf). Product decisions, architecture, and acceptance criteria are locked in the documents below. Implementation must follow those files, not reopen them.

## Documents

| File | What it is |
|---|---|
| [`docs/01-product-description.md`](docs/01-product-description.md) | Product scope, PIR types, search, persistence, interaction |
| [`docs/02-architecture.md`](docs/02-architecture.md) | MVC, `model` interface, event loop, `.pim` JSON, search-then-update sequence |
| [`docs/03-acceptance.md`](docs/03-acceptance.md) | Observable criteria for US1–US11, tests, ZIP contents, demo script |
| [`CONTEXT.md`](CONTEXT.md) | Domain glossary (PIR, Id, Alarm, Current Result, …) |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`AGENTS.md`](AGENTS.md) | Rules for AI agents: precedence, scope, architecture, gates |

Use the glossary terms as written. Do not treat **Name** as a title, **Label** as identity, or **Note** as a field name.

## Product in one paragraph

A single-user terminal PIM. The user manages Notes, Tasks, Events, and Contacts in a Working Collection, searches with contains / time comparison / `&&` `||` `!`, and stores the collection in a UTF-8 JSON file with the extension `.pim`. Python 3 and the standard library only. No GUI, no third-party TUI, no recurrence, no network.

## Planned layout

```
model/          # required package name; the unit-test surface
view/           # designed terminal UI and in-process Alarm Alerts
controller/     # one user action → model.PIM
pim.py          # composition root: python pim.py
tests/          # unittest for model only
docs/
CONTEXT.md
README.md
```

Code packages are not in the tree yet. Create them as specified in the architecture document.

## Constraints that affect every commit

- Importable top-level package named `model`
- Standard library only (no pip dependencies)
- Default timezone: Hong Kong Time (`Asia/Hong_Kong`)
- Failed commands do not mutate data, dump a traceback, or exit
- Unit tests target `model/` with `unittest`; line-coverage report at the source root

## Submission

One ZIP by **20:00, 20 November 2026**: SRS, design document, source, manuals, ≤4 min system video, requirements coverage table, model tests and coverage report, presentation PDF and ≤5 min recording, Honour Declaration at the ZIP root.

Checklist and demo script: [`docs/03-acceptance.md`](docs/03-acceptance.md).
