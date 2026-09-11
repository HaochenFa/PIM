# Technical Architecture

This is the architecture the assignment’s design document must explain: the chosen pattern, the main code parts and how they relate, and the collaboration for “search then update”. Implementation follows this file. Domain meaning follows `docs/PRODUCT.md` and `CONTEXT.md`.

---

## 1. Architectural pattern: MVC

**MVC** is the pattern. The assignment defines the system model as a separate package and as the only required unit-test surface. MVC keeps testable domain rules (PIR, criteria, store/load) away from terminal I/O (threads, ANSI, keyboard).

Not a web layered architecture. Not an extra hexagonal port for the filesystem: persistence is a local file, and tests use a temporary file (local-substitutable). A one-implementation `Storage` interface would be a fake seam.

### How the parts are instantiated

`pim.py` is the composition root:

1. Construct `model.PIM()` — empty Working Collection, no Bound File.
2. Construct `controller.App(pim)`.
3. Construct `view.Terminal(app)`.
4. `Terminal.run()` starts the event loop.

Then: View reads input → Controller calls `PIM` → View draws from PIM state. `model` does not import `view` or `controller`.

```
                    pim.py
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       PIM()       App(pim)    Terminal(app)
          ▲            │            │
          └────────────┘            │
                calls               │
          ◄─────────────────────────┘
                renders from PIM state
```

## 2. Package layout

The assignment requires the model in a package named `model`, and the other major parts to be identifiable in the source. Three sibling top-level packages, not `pim.model`:

```
model/                 # test surface. no threads, no stdin, no ANSI
  __init__.py          # exports PIM, Criterion constructors, PIR types
  pim.py               # Working Collection, dirty, bound path, save/load, due_alarms
  pir.py               # PIR hierarchy
  criterion.py         # composite criteria: And/Or/Not/Type/Contains/Time
  pimfile.py           # JSON codec (still model: US10/US11 are domain)
view/
  __init__.py
  terminal.py          # layout, event loop, Alarm Alert, dismissed set
  stdin_reader.py      # puts one line string on a Queue
controller/
  __init__.py
  app.py               # one user action → PIM call
  errors.py            # user-facing failures (no traceback leak)
pim.py                 # python pim.py
tests/                 # model only; inject now and temp .pim files
```

`model` is a deep module: callers use `PIM` and the Criterion constructors. Matching internals in `pir.py` / `criterion.py` are not the Controller’s interface.

## 3. `model` interface

```text
PIM
  create_note(text) -> Note
  create_task(description, deadline=None) -> Task
  create_event(description, start, alarms=None) -> Event
  create_contact(name, address=None, mobile=None) -> Contact
  modify(id, fields) -> PIR          # cannot change type; omitted fields stay
  delete(id) -> None
  get(id) -> PIR
  all() -> list[PIR]
  search(criterion) -> list[PIR]
  due_alarms(now) -> list[DueAlarm] # now is injected
  save(path) -> None
  load(path) -> None
  is_dirty() -> bool
  bound_path() -> str | None
```

Failures are explicit domain exceptions (`NotFound`, `ValidationError`, `ParseError`, `DirtyLoadError`, …) that the Controller turns into a status line. `due_alarms` does not sleep, does not read the wall clock, and does not write dismissed — dismissed lives in the View.

### PIR hierarchy

```
PIR (id)
├── Note (text)
├── Task (description, deadline?)
├── Event (description, start, alarms[])
└── Contact (name, address?, mobile?)
```

Shared: `id`, `type_name`, `display_name`, `text_fields()` (for unqualified contains), `modify(fields)`. Time fields and the alarm list exist only on the subclasses that own them.

### Search Criterion (composite)

```
Criterion.matches(pir) -> bool
├── TypeIs(note|task|event|contact)
├── Contains(field|ANY, needle)      # casefold substring
├── TimeCompare(field, op, instant)  # missing field → False; alarm → any effective instant
├── And(c1, c2)
├── Or(c1, c2)
└── Not(c)
```

`parse_criterion(s) -> Criterion` and `matches` both live in `model/criterion.py`. US7 syntax and semantics are part of the system model and must be unit-testable without the View. The Controller passes the line to `parse_criterion` then `search`. Tests may build the tree directly or go through the string.

## 4. View event loop

The main thread must not block on timeout-free `input()`, or Alarm Alerts appear only after Enter. The PIM also must not start a second OS process.

```
stdin reader thread (daemon)
    readline → Queue.put(line)

main loop (only thread that calls model)
    loop:
        due = pim.due_alarms(now)
        if snapshot changed: render()          # includes OVERDUE / SOON banner
        line = queue.get(timeout=0.5)
        if line: controller.handle(line); render()
```

Constraints:

- T = 500ms.
- Do not repaint the whole screen every tick; repaint only when the due set, dismissed set, Working Collection, Bound File, Current Result, selection, or status line changes.
- The reader thread never touches `PIM`. No lock.
- dismissed: in-memory View `set[(event_id, alarm_index)]`, not stored in the file.

## 5. PIM File JSON

```json
{
  "format": "pim/v1",
  "next_id": 5,
  "pirs": [
    { "id": 1, "type": "note", "text": "buy milk" },
    {
      "id": 2,
      "type": "task",
      "description": "submit ZIP",
      "deadline": "2026-11-20T20:00:00+08:00"
    },
    {
      "id": 3,
      "type": "event",
      "description": "COMP3211 lecture",
      "start": "2026-09-14T18:30:00+08:00",
      "alarms": [
        { "kind": "relative", "amount": 1, "unit": "day" },
        { "kind": "relative", "amount": 0, "unit": "minute" },
        { "kind": "absolute", "at": "2026-09-13T09:00:00+08:00" }
      ]
    },
    {
      "id": 4,
      "type": "contact",
      "name": "Ada",
      "address": null,
      "mobile": "12345678"
    }
  ]
}
```

`unit` ∈ {`minute`, `hour`, `day`, `week`}. `amount == 0` means at start. Optional fields may be `null` or omitted; load treats them the same. Unknown `format` or bad JSON → load fails; the Working Collection is unchanged.

## 6. Example collaboration: search then update

The assignment asks for a process diagram of searching for and updating records.

```mermaid
sequenceDiagram
    actor User
    participant V as view.Terminal
    participant C as controller.App
    participant P as model.PIM
    participant F as PIM File

    User->>V: criterion type = event && description contains "COMP"
    V->>C: handle(search line)
    C->>P: parse_criterion(line)
    P-->>C: And(TypeIs(event), Contains(description, "COMP"))
    C->>P: search(criterion)
    P-->>C: [Event id=3, ...]
    C-->>V: Current Result = matches
    V-->>User: list shows hits only

    User->>V: select 3
    User->>V: modify, new start (empty enter keeps description)
    V->>C: handle(modify 3, fields)
    C->>P: modify(3, {start: ...})
    Note over P: validate start; recompute Relative effective instants; dirty=true
    P-->>C: Event id=3
    C-->>V: detail refreshed
    V-->>User: new start and new Effective Alarm Time

    User->>V: save
    C->>P: save(bound_path)
    P->>F: write UTF-8 JSON
    P-->>C: dirty=false
```

The diagram shows: the criterion is evaluated in model, modify keeps the Id, Relative alarms move with start, persistence goes only through `PIM.save`.

## 7. Dependencies and tests

| Layer | Allowed | Forbidden |
|---|---|---|
| model | `json`, `datetime`, `zoneinfo`, `pathlib` | `threading`, stdin, ANSI, third-party libraries |
| view | `threading`, `queue`, `sys.stdin`, clear/ANSI | business rules, JSON schema |
| controller | calls model; maps exceptions to messages | reading/writing files itself; implementing contains |

Unit tests (the assignment requires tests for the model only):

- Create / validate / modify / delete for all four types
- Id is stable and not reused
- contains casefold, unqualified contains, missing-field time compare, and/or/not, existential match on several alarms
- save/load round-trip (temp directory)
- `due_alarms(now)` OVERDUE / SOON boundaries (injected now)
- dirty flag; a bad file must not clobber memory

The line-coverage report is for `model/` and lives in the source root.

## 8. Mapping to the rubric

- **Modularity / extendibility**: a new PIR type is a new subclass plus field metadata; Criterion and Controller do not grow an if-forest.
- **Justifiability**: MVC follows the assignment’s `model` package and unit-test rule; JSON is stdlib and verifiable; the event loop exists so in-process alerts work without a daemon.
- **Efficiency**: the Working Collection is in memory; search is a linear scan (personal-scale data; no index).
- **Stdlib only**: no pip dependencies.
