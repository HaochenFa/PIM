# AGENTS.md

Durable instruction set for AI agents working in this repository.

This is not a quick-start and not an implementation snapshot. User-facing overview is `README.md`. Product, architecture, and acceptance are locked in `docs/`. If this file and those documents diverge, fix this file — do not silently “improve” the product.

## Precedence

If anything conflicts, follow this order:

1. `Project Description.pdf` (the COMP3211 brief; cannot be waived)
2. `docs/01-product-description.md`
3. `docs/02-architecture.md`
4. `docs/03-acceptance.md`
5. `CONTEXT.md`
6. `docs/adr/`
7. `AGENTS.md`
8. `README.md`

Do not reopen locked decisions. Do not add ADRs that contradict accepted ones. If a genuine conflict with the brief appears, stop and tell the user; do not patch around it.

## Project intent

This is a **course group project**: a command-line Personal Information Management (PIM) system. The goal is full marks on the brief (SRS, design, implementation, model unit tests, presentation) — not a product beyond Appendix B.

The runnable system must let a user:

- create four PIR types (Note, Task, Event, Contact),
- modify, delete, and print them,
- search with type, contains, time comparison, `&&` `||` `!`,
- save and load a `.pim` file.

Visible demo quality (designed terminal UI, in-process Alarm Alerts) is in scope. Extra features are not.

## Non-negotiable scope

Implement exactly Appendix B (US1–US11) plus the HCI already decided: prompted create/modify, criterion-line search, in-process OVERDUE/SOON alerts.

**Out of scope** (do not implement, suggest, or leave stubs for):

- GUI, curses, Textual, Rich, prompt_toolkit, Click, colour libraries
- any pip / third-party dependency
- networking, multi-user, sync, daemon process, OS notifications (`osascript`, etc.)
- recurring events / Series / RRULE
- links between PIRs
- unique labels, a global title field, fuzzy (edit-distance) search
- changing a PIR’s type after creation
- snooze / postpone, live ringing, background timers as a second process

If a user or another agent asks for an out-of-scope feature, refuse it against this list and the brief’s “no extra credit for additional features” rule.

## Source of truth by topic

| Topic | Read |
|---|---|
| Domain words | `CONTEXT.md` |
| Fields, search grammar, interaction | `docs/01-product-description.md` |
| Packages, `PIM` interface, JSON schema, event loop | `docs/02-architecture.md` |
| Observable tests, fixture, ZIP, demo script | `docs/03-acceptance.md` |
| Why a choice was made | `docs/adr/0001`–`0015` |

Use glossary terms as written. Forbidden substitutions:

- **Name** is the Contact person name only — not a title on other types
- **Label** is not a concept in this product
- **Note** is a PIR type, not a field; the Note body field is `text`
- **Id** is the only unique identity; row numbers and Display Name are not

## Architecture rules

- Pattern: **MVC**. Composition root is `pim.py`: `PIM()` → `App(pim)` → `Terminal(app)` → `run()`.
- Top-level packages named `model`, `view`, `controller`. Not `pim.model`.
- `model` is a **deep module**. Callers and tests use `PIM` plus Criterion constructors. Matching, JSON codec, and validation stay inside `model`.
- `model` must not import `view` or `controller`. No threads, stdin, or ANSI in `model`.
- `parse_criterion` lives in `model` so US7 is unit-testable without the View.
- Persistence is JSON in a `.pim` file via `PIM.save` / `PIM.load`. Tests use a temp file. Do not add a one-implementation `Storage` port.
- `due_alarms(now)` is a pure query; **inject `now`**. `model` must not read the wall clock.
- View owns the event loop: daemon stdin-reader thread + main loop `Queue.get(timeout=0.5)`. Only the main thread calls `model`. Redraw on change, not every tick.
- Dismissed alerts are View memory, not part of the PIM File.

## Implementation guardrails

- Python 3, **standard library only**. No `requirements.txt` of third-party packages.
- Default timezone: IANA `Asia/Hong_Kong` (HKT). All datetimes timezone-aware. Compare instants.
- Failed commands are atomic: no mutation, no traceback to the user, no process exit. One specific English status-line error.
- Whitespace-only strings are missing values. Missing required fields fail the command.
- Ids are monotonic integers, persisted, never reused after delete.
- Relative alarms: at start or before start only. Search `alarm` is existential over Effective Alarm Times.
- contains: `str.casefold()` substring, not locale and not fuzzy.
- A time comparison on a missing field is false.
- Save appends `.pim` if omitted; load rejects other extensions.
- Dirty load/quit: save / discard / cancel — never silent drop.
- `print all` prints **Current Result**, not the unfiltered collection.
- Developer manual platform: macOS.
- User-facing strings and error messages: English.
- Course artefacts this agent writes (SRS, design text, comments that explain behaviour): English.

## Testing rules

- Framework: `unittest` (the brief’s example). Automatically executable, all passing.
- Test **`model` only** unless the user explicitly asks for more. The brief grades model unit tests.
- Each test must state the behaviour it exercises (name or comment) and assert expected results.
- Cover: four types create/validate/modify/delete; Id stability; contains / unqualified contains / missing-field time / and-or-not / multi-alarm; save/load round-trip; `due_alarms` with injected `now`; dirty flag; corrupt file does not clobber memory.
- Prefer the fixture in `docs/03-acceptance.md` section 4.
- Line-coverage report for `model/` belongs at the source root when asked to produce it.

## Agent working rules

- Implement the locked design. Do not “simplify” by collapsing MVC, swapping JSON for pickle, or blocking on `input()`.
- Do not start coding a new PIR type, a fifth package, or a TUI framework to make the UI “nicer”.
- When implementing, keep `model` the test surface: if a rule cannot be tested through `PIM` / Criterion, it is in the wrong package.
- If you must choose a detail not in the docs (e.g. exact menu keystrokes), pick the smallest option that still satisfies acceptance, and record it in a new ADR only if it is hard to reverse, surprising, and a real trade-off.
- Do not update `CONTEXT.md` with implementation types, file paths, or Python names. Glossary is domain only.
- Do not rewrite `docs/01`–`03` or accepted ADRs unless the user explicitly changes a product decision.
- Honour Declaration: GenAI use is allowed if acknowledged. Do not invent a false “no GenAI” claim. Contribution splits are the group’s, not the agent’s.

## Required gates

Before calling implementation work done:

1. `docs/03-acceptance.md` sections 1–3 are met (stories, alerts, NFRs).
2. `python -m unittest` is green.
3. `python pim.py` can run the demo script in `docs/03-acceptance.md` section 6 on macOS with stdlib only.
4. No third-party imports anywhere in the submitted source.

SRS, typeset design document, videos, and Honour Declaration are separate deliverables. Do not claim those are done when only code is done.

## Decision rule

When uncertain:

**assignment compliance > locked product/architecture > testability of `model` > terminal polish**

If a change makes the UI prettier but violates “standard library only”, or adds a feature Appendix B does not ask for, reject it.
