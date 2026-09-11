# Implement COMP3211 CLI PIM

Greenfield implementation of the locked product. No new product decisions. No extra features.

**Sources of truth** (do not reopen): `Project Description.pdf` > `docs/PRODUCT.md` > `docs/ARCHITECTURE.md` > `docs/ACCEPTANCE.md` > `CONTEXT.md` > `docs/adr/` > `AGENTS.md`.

Repo today: one commit (`INIT (PLAN)`), documents only, Python 3.12.4 on macOS. Packages `model/`, `view/`, `controller/`, `pim.py`, and `tests/` do not exist.

---

## Scope of this build

**In**

- Runnable `python pim.py` covering US1–US11 plus in-process OVERDUE/SOON alerts.
- `model/` as the deep test surface; `unittest` green on the acceptance fixture.
- Line-coverage report for `model/` at the source root (stdlib `trace`, no pip).
- Short macOS developer + user notes so the demo script is runnable.
- Align README/AGENTS paths with the real doc filenames (`PRODUCT.md`, `ARCHITECTURE.md`, `ACCEPTANCE.md`).
- One small ADR for the command vocabulary (the only remaining reversible UI choice).

**Out** (later, not this build)

- Typeset SRS / design document / coverage-table polish beyond a source-root stub.
- Presentation PDF, videos, Honour Declaration.
- GUI, curses, Textual/Rich, pip, recurrence, PIR links, OS notifications, snooze.

---

## Hygiene first

README and AGENTS currently point at `docs/01-product-description.md` etc. The tree has `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/ACCEPTANCE.md`. Update those two files to the real names. Do not rename or rewrite the product docs.

---

## Layout (locked)

```
pim.py                 # composition: PIM() → App(pim) → Terminal(app) → run()
model/
  __init__.py          # PIM, PIR types, Criterion constructors, parse_criterion, errors
  pim.py               # Working Collection, dirty, bound path, save/load, due_alarms
  pir.py               # PIR hierarchy, Alarm tagged union, datetime parse
  criterion.py         # composite tree + recursive-descent parser
  pimfile.py           # UTF-8 JSON codec, format pim/v1
view/
  __init__.py
  terminal.py          # regions, wizards, dismissed set, redraw-on-change
  stdin_reader.py      # daemon thread: readline → Queue
controller/
  __init__.py
  app.py               # one completed user action → PIM; holds Current Result + selection
  errors.py            # domain exceptions → one English status line
tests/                 # model only
docs/adr/0016-command-vocabulary.md
DEVELOPER.md           # macOS, Python 3.12, how to run tests + coverage
USER.md                # commands, prompts, errors
coverage.txt           # generated, source root
```

`model` must not import `view` or `controller`. No threads, stdin, or ANSI in `model`. No third-party imports anywhere.

---

## Model interface (locked signatures)

```text
PIM
  create_note(text) -> Note
  create_task(description, deadline=None) -> Task
  create_event(description, start, alarms=None) -> Event
  create_contact(name, address=None, mobile=None) -> Contact
  modify(id, fields) -> PIR          # type forbidden; omitted keys stay
  delete(id) -> None
  get(id) -> PIR
  all() -> list[PIR]                 # increasing Id
  search(criterion) -> list[PIR]     # increasing Id
  due_alarms(now) -> list[DueAlarm]  # now injected; no clock, no dismiss
  save(path) -> None                 # append .pim if missing; bind; dirty=false
  load(path, *, force=False) -> None # reject non-.pim; DirtyLoadError if dirty and not force
  is_dirty() -> bool
  bound_path() -> str | None
```

**Exceptions** (in `model`, re-exported): `NotFound`, `ValidationError`, `ParseError`, `DirtyLoadError`, `FileFormatError`, `ExtensionError`. Controller maps them to a status line. Failed commands do not mutate, dump a traceback, or exit.

**`force=True`** is the discard path. The View never calls `load` while dirty without save or force. This is how `DirtyLoadError` stays a domain rule instead of a View check only.

---

## Implementation details not in the docs (assignment + smallest option)

These are chosen so coding can start. They do not add product capability. Record the command language as **ADR-0016**; leave the rest as code comments / USER.md.

### Identity, time, alarms

- Ids start at 1, monotonic via persisted `next_id`, never reused.
- All datetimes timezone-aware. Bare input → `Asia/Hong_Kong`. Stored and compared at **minute** resolution (seconds/microseconds zeroed).
- Accepted input: `YYYY-MM-DDTHH:MM[:SS][offset|Z]`, `YYYY-MM-DD HH:MM`, date-only → that date 00:00 HKT.
- Relative alarm units: `minute|hour|day|week`. `amount == 0` is at start. Amount must be ≥ 0; relative-after-start is a `ValidationError`.
- `DueAlarm`: `event_id`, `alarm_index`, `at`, `status` (`OVERDUE` if `at <= now`, else `SOON` if `now < at <= now+15min`), plus `description` for the banner. OVERDUE wins on the boundary. `due_alarms` does not know about dismiss.

### Strings and optional fields

- Whitespace-only → missing. Missing required field → `ValidationError`, collection unchanged.
- Optional fields may be `null` or omitted in JSON; load treats them the same.
- Modify UI: empty enter keeps. Sentinel `none` on an optional field clears it (needed after a deadline/alarm was set). Not a new PIR field.

### Search parser (`model/criterion.py`)

Recursive descent. Grammar as in PRODUCT.md. Extra parse rules:

- `contains` needles are double-quoted; `\"` and `\\` allowed.
- After `<` `>` `=`, the datetime token runs until `&&` `||` `)` or end (unquoted ISO as in the fixture).
- Field names and `type` values are matched with `casefold`.
- Unqualified `contains` uses `PIR.text_fields()`.
- `alarm` is existential over Effective Alarm Times.
- Missing time field → that atom is false.
- Syntax error → `ParseError`; `PIM.search` is not called; Current Result unchanged (Controller).

### Persistence

- Schema exactly as ARCHITECTURE §5 (`format: "pim/v1"`).
- Write: temp file in the same directory then `os.replace` (atomic on the same volume).
- `save` to Bound File: no confirm. `save as` onto an existing path: View confirms, then `save`.
- Unknown `format`, bad JSON, or schema error → `FileFormatError`; memory unchanged (load into a side structure, swap only on success).
- Dismissed alerts are not in the file.

### Current Result and selection (Controller)

- Current Result lives in `App`, not in `PIM`.
- No active criterion → `all()`. Successful search stores the criterion and the hit list.
- `clear` drops the criterion and restores `all()`.
- After create/modify/delete: if a criterion is active, re-run it; else `all()`. Keeps the list honest without putting search state in `model`.
- Selection: 1-based **row of Current Result**, or `id <n>`. Row numbers are not identity. Unknown Id / empty selection on modify/delete/print-one → fail.

### Command vocabulary (ADR-0016)

Designed terminal, verb commands, prompted wizards for multi-field flows:

| Line | Action |
|---|---|
| `create` / `create note\|task\|event\|contact` | Start create wizard |
| `search <criterion>` or `search` then a criterion line | US7 |
| `clear` | Restore whole collection |
| `<n>` | Select row n of Current Result |
| `id <n>` | Select by Id |
| `modify` | Modify wizard on selection |
| `print` / `print all` | US8 (`print all` = Current Result) |
| `delete` | Confirm `y`/`n` |
| `save` / `save as <path>` / `load <path>` | US10–US11 |
| `dismiss` | Dismiss the first listed undismissed due alarm `(id, index)` |
| `help` | Command list |
| `quit` | Dirty prompt: `save` / `discard` / `cancel` |

Unknown command → status-line error, no mutation.

### View

- Regions: title (bound path or `untitled`, dirty `*`), Alarm Alert banner, Current Result table (`Id / type / Display Name / relevant time`), selection detail, status line, menu + prompt.
- ANSI clear/`\033[H` only when `stdout.isatty()`; otherwise reprint sections. No curses.
- Event loop: daemon stdin-reader thread puts lines on a `Queue`; main thread `get(timeout=0.5)`, calls `due_alarms(now)`, redraws **only on change** (due set, dismissed set, collection, bound path, Current Result, selection, status, wizard step).
- Only the main thread calls `model`. Reader never touches `PIM`. No lock.
- Dismissed: in-memory `set[(event_id, alarm_index)]`.
- Wizards (create/modify/alarms/confirmations) are View state: collect fields, then one Controller call. Event alarms: after start, loop “Add an alarm? [y/n]” → relative (amount+unit or `0` = at start) or absolute instant.
- Banner: all currently due undismissed alarms; `dismiss` pops the first.

### Print / Display Name

- Display Name (not stored): Note = first line of `text`; Task/Event = `description`; Contact = `name`.
- Print-one: every field; Event prints each alarm’s kind and Effective Alarm Time.

---

## Tests (model only, `unittest`)

Discoverable via `python -m unittest`. Names state the behaviour. Use the §4 fixture.

Must cover:

- Create/validate/modify/delete for all four types; whitespace-only required fields fail with no mutation.
- Id stable on modify; deleted Ids not reused; `next_id` persists.
- Type change via `modify` fails; PIR unchanged.
- Duplicate Contact names allowed.
- contains casefold; unqualified contains; `name contains "ada"` hits `Ada`.
- `deadline < T` excludes the no-deadline Task; `start = T` instant equality with default HKT.
- `alarm < T` existential; after start +7 days, relative effective times move, absolute does not.
- `&&` `||` `!` and parentheses, precedence `!` > `&&` > `||`; syntax error raises `ParseError`.
- Relative-after-start rejected.
- save/load round-trip (temp dir): Ids, types, fields, alarm kinds, effective instants, `next_id`.
- `save` appends `.pim`; `load` of other extension raises `ExtensionError` and does not parse.
- Bad JSON / unknown format: memory unchanged.
- `load` while dirty without `force` → `DirtyLoadError`.
- `due_alarms(now)`: OVERDUE at `at <= now`; SOON in `(now, now+15min]`; inject `now`.

Do not unit-test View/Controller unless a later request says so. The brief grades model tests.

Coverage: `python -m trace --count --summary -m unittest discover -s tests` (or a tiny stdlib helper) written to `coverage.txt` at the source root. No `coverage` package, no `requirements.txt`.

---

## Build sequence

Work in this repo on a branch `impl` (or on `main` if you prefer a single local history). Sequential slices so each leaves `unittest` green. Do not spawn a Graphite execute-plan stack: this is a course tree with no PR workflow, and later slices depend on the `PIM` interface.

1. **Doc path fix + ADR-0016** (command table above).
2. **`model/pir.py` + datetime/alarm + create/modify validation tests.**
3. **`model/pim.py` CRUD, Id, dirty (in-memory only) + tests.**
4. **`model/criterion.py` + `search` + fixture search tests.**
5. **`model/pimfile.py` + `save`/`load`/`due_alarms` + persistence and alarm-alert tests.**
6. **`controller/`** command dispatch, Current Result, exception mapping.
7. **`view/`** layout, stdin thread, 500ms loop, wizards, dismiss, dirty save/load/quit.
8. **`pim.py`**, `DEVELOPER.md`, `USER.md`, `coverage.txt`.
9. **Gates**: `python -m unittest`; `python pim.py` walked against ACCEPTANCE §6; grep for third-party imports.

Do not rewrite PRODUCT/ARCHITECTURE/ACCEPTANCE or CONTEXT.md with Python type names.

---

## Gates (definition of done for this build)

1. ACCEPTANCE.md sections 1–3 are demonstrable (stories, alerts, NFRs).
2. `python -m unittest` is green.
3. `python pim.py` can run the demo script in ACCEPTANCE.md §6 on macOS with stdlib only.
4. No third-party imports in submitted source; no `requirements.txt`.
5. `coverage.txt` exists at the source root and includes create/modify/delete/search/store-load/`due_alarms`.

SRS typesetting, presentation media, and Honour Declaration remain unclaimed.

---

## Decision rule while coding

`assignment compliance > locked product/architecture > testability of model > terminal polish`

If a nicer UI needs a pip package, or a feature Appendix B does not ask for, reject it.
