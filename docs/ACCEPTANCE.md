# Acceptance Criteria

Subject: the PIM implemented from `docs/01-product-description.md` and `docs/02-architecture.md`. Pass means every Appendix B user story is demonstrable and unit-testable, Appendix A quality items have evidence, and out-of-scope features are absent.

Each clause below is **observable**. A failed command must not change the Working Collection, must not print a traceback, and must not exit the process.

---

## 1. User stories

### US1 / US2 Note

- A Note with non-empty body can be created and receives a new Id.
- Empty or whitespace-only body → fail; collection unchanged.
- No title field. List Display Name = first line of the body.

### US3 Task

- A Task with a description can be created; deadline may be omitted.
- Missing description → fail.
- A Task with a valid ISO/HKT deadline can be found by a time comparison.

### US4 Event

- An Event with description and start can be created; zero alarms is allowed.
- The same Event can hold several Alarms: Relative (at start, or N minutes/hours/days/weeks before) and Absolute (a specific instant) may coexist.
- Relative after start is rejected.
- After changing start: Relative Effective Alarm Times move; Absolute times do not.
- Missing description or start → fail.

### US5 Contact

- A Contact with a name can be created; address and mobile may be omitted.
- Missing name → fail.
- Duplicate names are allowed.

### US6 Modify

- Fields are modified by Id; the Id does not change.
- Empty enter (UI) or omitted fields keep their previous values.
- Type cannot change. Attempting to change type → fail; the PIR is unchanged.
- Unknown Id → fail.

### US7 Search

On a fixed fixture, each criterion must yield a determined set (order may be fixed as increasing Id):

| Criterion | Must hold |
|---|---|
| `type = note` | Notes only |
| `text contains "x"` | casefold substring of the body |
| `contains "x"` | a hit on any text field includes the PIR |
| `name contains "ada"` matches `Ada` | casefold |
| `deadline < T` / `>` / `=` | only Tasks that have a deadline |
| Task with no deadline | does not match `deadline < T` |
| `start = T` | instant equality (including default HKT) |
| `alarm < T` | the Event is included if any Effective Alarm Time matches |
| `A && B` `A \|\| B` `!A` and parentheses | precedence `!` > `&&` > `\|\|` |
| Syntax error | error reported; Current Result unchanged |

Out: fuzzy match, locale case rules, Series.

### US8 Print

- With a selection → print every field of that PIR (for an Event, print each Alarm’s kind and Effective Alarm Time).
- `print all` → print every PIR in Current Result, not the whole collection ignoring search.
- Print-one with no selection → fail.

### US9 Delete

- After selection, confirm y → that Id is gone; confirm n → unchanged.
- Deleted Ids are not reused; later creates still increment.
- No selection / bad Id → fail.

### US10 / US11 Store and load

- `save as path` appends `.pim` if missing; on disk the file is UTF-8 JSON with `format` `pim/v1`.
- `load` of a non-`.pim` path → fail, no parse.
- save → load round-trip: Id, type, fields, Alarm kinds, and effective instants match.
- Load or quit while dirty: the user must choose save / discard / cancel; cancel leaves state unchanged.
- `save` overwrites the Bound File without asking; `save as` overwriting another existing file asks.
- Bad JSON / unknown format → load fails; memory unchanged.

---

## 2. Alarm Alert (in-process)

While the View is running, without a second process:

- Effective Alarm Time ≤ now → OVERDUE until dismissed (inject `now` or wait on the real clock).
- Effective instant in (now, now+15min] → SOON.
- After dismiss, that (Id, alarm) is not shown again in this process; nothing is written to `.pim`.
- Main-loop tick is 500ms; with no keyboard input the banner still appears within 500ms (tests may inject `now` and run one loop).
- No `osascript`, no other OS notification, no second Python process.

---

## 3. Non-functional / assignment constraints

| Item | Acceptance |
|---|---|
| Language | Python 3, standard library only (no third-party `requirements.txt`) |
| Packages | Importable top-level package `model`; identifiable `view` and `controller` |
| Tests | `unittest`, automatically executable, all pass; comments or names state the behaviour; assertions state expected results |
| Coverage | Line-coverage report for `model/` at the source root |
| Interaction | Terminal; no GUI window |
| Errors | Invalid input does not crash, exit, or mutate data |
| Platform | Developer manual guarantees one platform (macOS) |
| Extra features | No Textual/Rich, no recurrence, no PIR links, no OS notifications |

---

## 4. Fixture (use in tests)

Create in advance:

1. Note id=1 text=`Shopping: Milk`
2. Task id=2 description=`Submit PIM` deadline=`2026-11-20T20:00:00+08:00`
3. Task id=3 description=`Inbox` no deadline
4. Event id=4 description=`COMP3211 lecture` start=`2026-09-14T18:30:00+08:00`  
   alarms: relative 1 day; relative 0 minute; absolute `2026-09-13T09:00:00+08:00`
5. Contact id=5 name=`Ada` mobile=`12345678` no address
6. Contact id=6 name=`Ada` address=`HK` no mobile

Expected examples:

- `type = contact && name contains "ada"` → {5,6}
- `deadline < 2026-11-21T00:00:00+08:00` → {2}, not 3
- `description contains "comp3211"` → {4}
- `alarm < 2026-09-13T18:00:00+08:00` → {4} (only the absolute 09:00 matches; relative 1 day = 13th 18:30 is not before 18:00)
- Change id=4 start by +7 days → relative effective instants shift by 7 days; absolute stays 09-13 09:00
- Delete id=2 then create a note → new Id ≥ 7, never 2

---

## 5. Deliverable checklist (ZIP, 20:00 20 Nov 2026)

The assignment requires a single ZIP. The archive root must contain:

| Deliverable | Points | This project |
|---|---|---|
| SRS | 6 | Expand the product description into a full SRS (omit System models / System evolution / Appendix / Index) |
| Design document | 5 | Expand the architecture doc: architecture diagram, classes/methods, search-and-update sequence diagram, textual explanation |
| Source + developer manual + user manual + ≤4 min MP4 + requirements coverage table | 6 | `model/` `view/` `controller/` `pim.py`; manuals for macOS + the Python version used; coverage table at source root |
| Unit tests for the model + line-coverage report | 4 | `tests/` + coverage file at source root |
| Presentation PDF + ≤5 min MP4 | 4 | Each member ≥1 minute; face + student ID; contents: create a PIR, define a search criterion, run a search, overall design, one lesson learned |
| Honour Declaration | required | At ZIP root; GenAI reported honestly; four-person contribution 25% each is the safe split. Missing or false declaration: up to 30% penalty |

The coverage table has at least two columns: Appendix B stories and SRS requirement ids, marked implemented / not implemented. These criteria require **US1–US11 all implemented**. The “not implemented” column should be empty, or list only explicit out-of-scope extras.

---

## 6. Demo script (system video / presentation, ≤4 minutes)

1. Start: untitled, empty list.
2. Create the fixture Note, Task (no deadline), Event (two relative + one absolute), Contact.
3. Search `type = event && description contains "COMP"`; the list shows only that Event.
4. Select it, change start; show Relative effective times moving and Absolute staying.
5. `print` that PIR.
6. `save as demo.pim`, quit, load again; the Id is still there.
7. If time allows: one illegal criterion, one blocked dirty load, one Alarm Alert (align the clock or inject `now` into the SOON window).

Do not demo a GUI. Do not demo recurrence.

---

## 7. Definition of done

Implementation is done for a full-mark attempt when all of the following hold — not when more features could still be added:

1. `python -m unittest` is green; a `model/` line-coverage report exists and covers create/modify/delete/search/store-load/`due_alarms`.
2. On the macOS + Python version in the developer manual, `python pim.py` runs section 6 using the standard library only.
3. Every clause in sections 1–3 is reproducible in the UI or in tests.
4. Source root has the requirements coverage table and the coverage report; no third-party dependencies.
5. A four-person presentation can fit in 5 minutes: one create requirement, one criterion requirement, one search, the MVC shape, one lesson (suggested lesson: US7 is only testable if the model is separated from I/O).

Still later, not product decisions: typeset SRS, typeset design document, recordings, Honour Declaration. Those follow the assignment templates, using these three planning documents as the source of truth.
