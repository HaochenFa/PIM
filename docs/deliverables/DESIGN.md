---
title: "Design Document — Personal Information Management (PIM) System"
subtitle: "COMP3211 Software Engineering, Fall 2026 — Group Project"
date: "Version 1.1 draft, 24 September 2026"
---

<!-- Source-tree note (not rendered): docs/ARCHITECTURE.md is the working
architecture reference; this document is the submitted design. Section 5 is the
only record of design decisions. -->

Requirement ids such as FR-16 refer to the Software Requirements Specification (SRS).

# 1. Introduction

This document describes the design of the command-line PIM system:

- **Section 2:** the architecture: which pattern was chosen, why, and how it is instantiated.
- **Section 3:** the main code components: every class with its fields and public methods, and how the classes relate.
- **Section 4:** one example use, *search for records and then update one*, as a sequence diagram.
- **Section 5:** the design decisions, each with its reason and the alternatives rejected.
- **Section 6:** a short assessment of modularity, efficiency, extendibility, and justifiability.

The system is written in Python 3.12 and uses only the standard library. All type names below are Python types. `X | None` means "an X, or nothing"; `list[X]` is a list of X; `dict[K, V]` is a mapping.

# 2. Architecture

## 2.1 Chosen pattern: Model–View–Controller

The system uses the **Model–View–Controller (MVC)** pattern. Each of the three components is a top-level Python package: `model`, `view`, and `controller`.

![Architecture of the PIM system (MVC). Solid arrows are calls; dotted arrows from `pim.py` show object creation; the dotted arrow from the View is read-only use of model value objects.](diagrams/architecture.png){width=100%}

**Why MVC.** Four reasons:

1. **The brief asks for it.** All model code must be in a separate package named `model` so that it can be unit-tested. MVC is the pattern that draws exactly that line: the model holds the data and the rules, and knows nothing about the screen.
2. **It fits an interactive program.** The PIM is a loop: read one user action, change the data, and show the new state. MVC splits that loop into three jobs. The View reads input and draws. The Controller turns one finished action into model calls. The Model applies the rules.
3. **Two front ends share one controller.** On an interactive terminal the View is a full-screen `curses` interface; for scripted input, such as the tests, it is a line-by-line interface. Both call the same `App`, so the behaviour cannot drift between them.
4. **Tests need no screen.** Search (US7), persistence (US10/US11), and alarms can be tested by calling `PIM` directly. The time `now` is passed in, so alarm tests do not depend on the wall clock.

**Alternatives considered.**

- *A layered architecture* (UI → service → storage) would need a separate storage layer and interface. With one JSON file format, that layer would have a single implementation and add indirection for nothing. In this design, persistence is two methods of the model (`save`, `load`).
- *A single procedural script* would mix parsing, input, and screen code, and it would miss the brief's `model`-package requirement.

## 2.2 How the components are instantiated

| Component | Package / class | Responsibility in this system |
|----------------|------------------------------------------------------------|----------------------------------------------------------------------|
| Model | `model.PIM`, the PIR classes, alarms, `Criterion`, `pimfile` | Holds the Working Collection and assigns Ids. Validates every field. Parses and evaluates search criteria. Reads and writes the PIM File. Computes due alarms for a given `now`. Raises a `PIMError` subclass on every rule violation. |
| Controller | `controller.App`, `controller.errors` | Handles one completed user action: create, modify, delete, search, print, save, load. Keeps the Current Result, the search criterion, and the Selection. Turns every model exception into one English status line; it never lets one reach the user as a traceback. |
| View | `view.Terminal`, `view.CursesUI`, helper modules | Owns the event loop (500 ms tick). Reads keys or lines. Asks for fields one at a time. Draws the title, Alarm Alert banner, list, detail, and status line. Remembers which alerts were dismissed. |
| Composition root | `pim.py` | `main()` creates `PIM()`, passes it to `App(pim)`, passes that to `Terminal(app)`, and calls `run()`. |

**Dependency rules.**

- `model` imports nothing from `view` or `controller`.
- `controller` imports `model` only.
- `view` calls `controller.App` for every action. It imports from `model` only value types and helpers: it displays `PIR` and `DueAlarm` objects, builds `RelativeAlarm` / `AbsoluteAlarm` values in the alarm prompts, and uses `HKT` for the clock.
- No module imports anything outside the Python standard library.

**Event loop.** The View runs the loop, and only its main thread calls the model:

- On a TTY, `CursesUI.loop` waits for a key with a 500 ms timeout.
- Otherwise, a daemon thread reads standard input into a `Queue`, and `Terminal` waits on the queue with a 500 ms timeout.

After each input or timeout, the View asks `App.due_alarms(now)` for alerts and redraws only if something changed.

# 3. Structure of and relationships among the main code components

## 3.1 Model classes

![Model classes, part 1: the Working Collection, the PIR hierarchy, and alarms.](diagrams/model-pir-classes.png){height=80%}

**Relationships.**

- `PIM` *aggregates* any number of PIRs, keyed by Id.
- `PIR` is an abstract base class with four concrete subclasses. Each subclass declares its fields in `FIELDS`, which the View uses to build the create and modify prompts.
- An `Event` is *composed of* zero or more alarms. Each alarm is a `RelativeAlarm` or an `AbsoluteAlarm`; both provide `effective(start)`.
- `PIM.due_alarms` *creates* `DueAlarm` value objects.

![Model classes, part 2: search criteria (Composite pattern) and the exception hierarchy.](diagrams/model-criterion-classes.png){width=100%}

**Relationships.**

- A search criterion is a tree built with the **Composite** pattern. Leaves (`TypeIs`, `Contains`, `TimeCompare`) test one PIR; `And`, `Or`, and `Not` combine sub-criteria.
- `parse_criterion` builds the tree from one line of text, using a recursive-descent parser whose precedence is `!` > `&&` > `||`. It raises `ParseError` on bad syntax.
- Every model failure is a subclass of `PIMError`. `status_message()` gives the English text that the Controller shows.

### Class `PIM` (module `model.pim`)

The Working Collection: PIR identity, search, persistence, and due alarms.

**Fields (private):**

- `_pirs: dict[int, PIR]`: PIRs keyed by Id.
- `_next_id: int`: the next Id to assign.
- `_dirty: bool`: whether there are unsaved changes.
- `_bound_path: str | None`: the Bound File.

| Return type | Method | Arguments | Exceptions | Description |
|--------------------------|--------------------------|----------------------------------------|----------------------------|----------------------------------------------|
| `Note` | `create_note` | `text: str \| None` | `ValidationError` | Creates and inserts a Note with the next Id; marks the collection dirty. |
| `Task` | `create_task` | `description: str \| None`, `deadline: datetime \| str \| None = None` | `ValidationError` | Creates a Task; the deadline is optional. |
| `Event` | `create_event` | `description: str \| None`, `start: datetime \| str \| None`, `alarms: list[AlarmSpec] \| None = None` | `ValidationError` | Creates an Event; rejects out-of-range alarm times (FR-8). |
| `Contact` | `create_contact` | `name: str \| None`, `address: str \| None = None`, `mobile: str \| None = None` | `ValidationError` | Creates a Contact. |
| `PIR` | `modify` | `pir_id: int \| str`, `fields: dict[str, object]` | `NotFound`, `ValidationError` | Copies the PIR, applies the fields to the copy, and replaces the original only if the copy is valid and different (atomic). |
| `None` | `delete` | `pir_id: int \| str` | `NotFound` | Removes the PIR. Its Id is never reused. |
| `PIR` | `get` | `pir_id: int \| str` | `NotFound` | Returns the PIR with this Id. |
| `list[PIR]` | `all` | — | — | Every PIR in Id order. |
| `list[PIR]` | `search` | `criterion: Criterion` | — | The PIRs for which `criterion.matches(pir)` is true, in Id order. |
| `list[DueAlarm]` | `due_alarms` | `now: datetime \| str` | `ValidationError` | OVERDUE and SOON alarms at the given `now`. Never reads the clock. |
| `None` | `save` | `path: str \| os.PathLike[str]` | `ValidationError`, `OSError` | Writes the PIM File atomically, appending `.pim` if missing and expanding a leading `~`; binds the path and clears the dirty flag. |
| `None` | `load` | `path: str \| os.PathLike[str]`, `force: bool = False` (keyword) | `ExtensionError`, `ValidationError`, `DirtyLoadError`, `FileFormatError` | Replaces the collection from a file. Parses fully before replacing, so a bad file changes nothing. |
| `bool` | `is_dirty` | — | — | True if there are unsaved changes. |
| `str \| None` | `bound_path` | — | — | Path of the last successful save or load. |

### Class `PIR` (abstract) and subclasses (module `model.pir`)

The base class of all records.

**Fields:**

- `id: int`
- `type_name: str` (class constant)
- `FIELDS: tuple[FieldSpec, ...]` (class constant)

| Return type | Method | Arguments | Exceptions | Description |
|------------------------|----------------------|------------------------|--------------------------|------------------------------------------------|
| `str` | `display_name` (property) | — | — | The derived list label (see the SRS glossary). |
| `list[str]` | `text_fields` | — | — | Every text value, used by unqualified `contains`. |
| `str \| None` | `text_value` | `field: str` | — | The named text field, or `None` if this type has no such field. |
| `list[datetime]` | `time_values` | `field: str` | — | The instants of `deadline`, `start`, or `alarm` (Effective Alarm Times); empty if missing. |
| `datetime \| None` | `relevant_time` | — | — | The deadline or start shown in the list. |
| `None` | `modify` | `fields: dict[str, object]` | `ValidationError` | Applies field changes in place. Rejects a change of type. |
| `dict` | `to_json` | — | — | The `pim/v1` JSON object. |
| `list[tuple[str, str]]` | `detail_lines` | — | — | (label, value) rows for `print`. |

The constructors of the subclasses:

| Subclass | Constructor arguments | Extra fields | Exceptions |
|--------------|--------------------------------------------------|--------------------------------------------|--------------------|
| `Note` | `pir_id: int`, `text: str \| None` | `text: str` | `ValidationError` |
| `Task` | `pir_id: int`, `description: str \| None`, `deadline: datetime \| str \| None = None` | `description: str`, `deadline: datetime \| None` | `ValidationError` |
| `Event` | `pir_id: int`, `description: str \| None`, `start: datetime \| str \| None`, `alarms: list[AlarmSpec] \| None = None` | `description: str`, `start: datetime`, `alarms: list[RelativeAlarm \| AbsoluteAlarm]` | `ValidationError` |
| `Contact` | `pir_id: int`, `name: str \| None`, `address: str \| None = None`, `mobile: str \| None = None` | `name: str`, `address: str \| None`, `mobile: str \| None` | `ValidationError` |

`Event` adds one method: `effective_alarm_times() -> list[datetime]`.

### Alarm classes (module `model.pir`)

| Class | Constructor | Fields | Methods |
|---------------------|------------------------------------------------|--------------------|------------------------------------------------|
| `RelativeAlarm` | `amount: int \| str`, `unit: str`. Raises `ValidationError` for a negative or non-integer amount, or a unit other than minute, hour, day, or week. | `amount: int`, `unit: str` | `effective(start: datetime) -> datetime` (start minus the duration); `to_json() -> dict`; `kind_label() -> str` |
| `AbsoluteAlarm` | `at: datetime \| str`. Raises `ValidationError`. | `at: datetime` | `effective(start: datetime) -> datetime` (returns `at`); `to_json() -> dict`; `kind_label() -> str` |
| `DueAlarm` | `event_id: int`, `alarm_index: int`, `at: datetime`, `status: str`, `description: str` | the same | `key() -> tuple[int, int]` (identity used for dismiss) |
| `FieldSpec` (dataclass) | `key: str`, `label: str`, `kind: str`, `required: bool = True` | the same | — |

`AlarmSpec` means `RelativeAlarm | AbsoluteAlarm | dict`. A `dict` is the JSON form read from a file.

### Criterion classes (module `model.criterion`)

| Class | Constructor | Fields | `matches(pir: PIR) -> bool` returns true when … |
|------------------|--------------------------------------------------|------------------------------|--------------------------------------------------|
| `Criterion` (abstract) | — | — | (abstract; raises `NotImplementedError`) |
| `TypeIs` | `type_name: str`. Raises `ParseError`. | `type_name: str` | the PIR's type is `type_name` |
| `Contains` | `field: str \| None`, `needle: str`. Raises `ParseError`. | `field: str \| None`, `needle: str` (case-folded) | the folded field value, or any text field when `field` is `None`, contains `needle` |
| `TimeCompare` | `field: str`, `op: str`, `instant: datetime`. Raises `ParseError`. | `field`, `op`, `instant` | any instant of `field` satisfies `op` against `instant`; false if there is none |
| `And` / `Or` | `left: Criterion`, `right: Criterion` | `left`, `right` | both / either child matches |
| `Not` | `inner: Criterion` | `inner` | the child does not match |

### Module-level functions of `model`

| Return type | Function | Arguments | Exceptions | Description |
|--------------------|------------------------|--------------------------------------|--------------------------|------------------------------------------|
| `Criterion` | `parse_criterion` | `text: str` | `ParseError` | Parses one US7 criterion line (grammar in SRS FR-16). |
| `datetime` | `parse_datetime` | `value: datetime \| str` | `ValidationError` | Parses ISO 8601 or `YYYY-MM-DD HH:MM`; defaults to HKT; floors to the minute. |
| `str` | `format_datetime` | `dt: datetime` | — | ISO 8601 text to the second. |
| `tuple[int, list[PIR]]` | `read_pim_file` | `path: str \| os.PathLike[str]` | `ExtensionError`, `ValidationError`, `FileFormatError` | Parses a PIM File without touching the collection. |
| `Path` | `write_pim_file` | `path: str \| os.PathLike[str]`, `next_id: int`, `pirs: list[PIR]` | `ValidationError`, `OSError` | Writes a temporary file, then atomically replaces the target. |

### Exceptions

All are subclasses of `PIMError(Exception)`, which provides `status_message() -> str`:

- `ValidationError`: a missing or illegal field value.
- `NotFound`: no PIR has this Id.
- `ParseError`: bad criterion syntax.
- `DirtyLoadError`: load with unsaved changes and no force.
- `FileFormatError`: the file is not a valid `pim/v1` PIM File.
- `ExtensionError`: the path does not end in `.pim`.

## 3.2 Controller and View classes

![Controller and View classes.](diagrams/controller-view-classes.png){width=100%}

**Relationships.**

- `CursesUI` drives a `Terminal` when a TTY is available.
- `Terminal` calls `App` for every user action.
- `App` calls `PIM`.

Neither `App` nor `Terminal` stores PIR data of its own. `App` stores only the Current Result (a list of PIR references), the criterion, and the Selected Id, and it re-runs the criterion after every change.

### Class `App` (module `controller.app`)

**Fields:**

- `pim: PIM`
- `status: str` and `status_kind: str` (`info`, `ok`, or `err`)
- `print_text: str`
- private: `_criterion: Criterion | None`, `_criterion_line: str | None`, `_result: list[PIR]`, `_selected_id: int | None`

The controller never raises: on failure it sets the status and returns `None` or `False`.

| Return type | Method | Arguments | Description |
|------------------------------------|------------------------------------------|------------------------------------------------------|----------------------------------------------------------------------|
| `PIR \| None` | `create` | `type_name: str`, `fields: dict[str, object]` | Creates a PIR and selects it. |
| `PIR \| None` | `modify` | `fields: dict[str, object]` | Modifies the selection. Empty `fields` changes nothing. |
| `bool` | `delete_selected` | — | Deletes the selection, after the View has confirmed. |
| `bool` | `search` | `line: str` | Parses and runs a criterion. On error, keeps the Current Result. |
| `None` | `clear_search` | — | Restores the whole collection. |
| `None` | `select_row` / `select_id` | `number: int \| str` / `pir_id: int \| str` | Selects by row of the Current Result, or by Id. |
| `str \| None` | `print_selected` | — | Detail text of the selection. |
| `str` | `print_all` | — | Detail text of every PIR in the Current Result. |
| `bool` | `save` | `path: str \| os.PathLike[str] \| None = None` | Saves to the Bound File or to `path`; the status names the absolute path. Reports `OSError` as a status. |
| `bool` | `load` | `path: str \| os.PathLike[str]`, `force: bool = False` | Loads and resets the search and the Selection; the status names the absolute path. |
| `list[DueAlarm]` | `due_alarms` | `now: datetime` | Passes through to the model. |
| `list[PIR]` / `PIR \| None` / `bool` | `current_result` / `selected` / `is_dirty` | — | State that the View reads to draw the screen. |
| `bool` | `would_overwrite` | `path: str \| os.PathLike[str]` | Whether `save as` would replace another existing file. |

`controller.errors.message_for(exc: BaseException) -> str` maps an exception to one status line:

- a `PIMError` → its `status_message()`;
- an `OSError` → its text;
- anything else → `command failed`.

### Class `Terminal` (module `view.terminal`)

**Fields:**

- `app: App`
- `stdin`, `stdout`: text streams
- `queue: Queue`
- `dismissed: set[tuple[int, int]]`
- `page_size: int`
- `_now`: an injected clock, for tests

| Return type | Method | Arguments | Description |
|--------------------|--------------------------|--------------------------------------------------|--------------------------------------------------|
| `None` | `run` | — | Starts `CursesUI` on a TTY, or else the line loop. Returns on quit. |
| `list[DueAlarm]` | `visible_due` | — | Due alarms minus the dismissed ones. |
| `None` | `render` | — | Draws the line-UI screen. |
| `None` | `ask` | `prompt: str`, `handler`, `kind: str \| None = None`, `chooser = None`, `picker = None`, `browser = None` | Queues a prompt; `handler(answer)` runs when the user answers. |
| `FileBrowser \| None` | `current_browser` | — | The folder browser of the current load or save-as prompt, if any. |
| `None` | `type_path_instead` | — | Drops the browser so the same prompt takes a typed path. |
| `None` | `apply_accelerator` | `action: str` | Runs the command bound to a single key. |

### Class `CursesUI` (module `view.curses_ui`)

**Fields:**

- `term: Terminal`
- `stdscr`: the curses window
- `theme: Theme`

It has one public method, `loop() -> None`: the full-screen event loop (`get_wch` with a 500 ms timeout). Every command runs through `_safe`, which turns any exception into a status line.

### View helper modules

| Module | Role |
|-------------------|----------------------------------------------------------------------|
| `view.layout` | Builds the screen model: title, banner, list rows, detail, and menu. |
| `view.widgets` | `Chooser` (a closed list of answers) and `DateTimePicker` (calendar and time). |
| `view.file_browser` | `FileBrowser`: folders and `.pim` files for load and save-as paths. Returns a path string, so the prompt handler validates it like a typed path (Section 5.4). |
| `view.keys` | Maps keys to actions (accelerators), e.g. `w` save, `W` save as, `o` load. |
| `view.theme` | Colour roles for 256-colour, 8-colour, and monochrome terminals. |
| `view.textwidth` | East-Asian-width-aware clipping and padding. |
| `view.stdin_reader` | Daemon thread that feeds lines into the `Queue` in the line UI. |

# 4. Example use: search for records, then update one

![Sequence diagram: searching for Events whose description contains "COMP", then changing the start of the hit.](diagrams/search-update-sequence.png){width=100%}

The numbers in brackets are the message numbers in the diagram.

**Search (messages 1–10).**

- *(1–2)* The user enters a criterion line. `Terminal` passes the raw line to `App.search`.
- *(3–4)* `App` calls `parse_criterion`, which tokenizes the line and builds the tree `And(TypeIs("event"), Contains("description", "comp"))`.
- *(5–8)* `PIM.search` calls `matches` on every PIR in Id order, and `And` evaluates its two children.
- *(9)* `App` stores the criterion and the hits as the Current Result, selects the first hit, and sets the status `1 match(es)`.
- *(10)* The View redraws the list and the detail pane.

A syntax error would raise `ParseError` at message 3. `App` would then leave the Current Result as it was and show `search syntax error: …`.

**Update (messages 11–30).**

- *(11–15)* `modify` asks `App` for the Selection. `Terminal` then prompts field by field, using the Event's `FIELDS`; an empty answer keeps a value.
- *(16–17)* `App.modify` sends only the changed fields to `PIM.modify`.
- *(18–20)* The model uses **copy-then-replace**: it copies the Event and applies the change to the copy. The copy parses the new start and checks that every Effective Alarm Time is still in range.
- *(21–26)* **If the copy is valid:** `PIM` puts the copy in place of the original under the same Id and marks the collection dirty. `App` then re-runs the stored criterion, so the Current Result is up to date, and the View shows the new start and the moved relative alarm times.
- *(27–30)* **If validation fails:** the exception propagates before the original is touched. `App` shows the message, and the data is exactly as before (FR-15, NFR-4).

The diagram shows the main design points of the system:

- the criterion is parsed and evaluated inside the model;
- the Controller holds the Current Result;
- the Id never changes;
- relative alarms follow the start;
- a failed update is atomic.

# 5. Design decisions

Each table below records one group of decisions: what was decided, why, and what was rejected. Section 2.1 covers the choice of MVC itself.

## 5.1 Platform and libraries

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| Python 3.12 with the standard library only. | The brief allows Java or Python and grades use of the standard library only. Python is the language the group knows best. | Java: nothing in the brief favours it. Any pip package, for example Textual, Rich, or pytest. |
| A full-screen `curses` interface on an interactive terminal, and a plain line interface when input or output is redirected (or `PIM_NO_CURSES=1`). | The brief asks for a command-line system and gives no credit for a GUI. `curses` is in the standard library. The line interface lets tests inject `stdin`, `stdout`, and `now`. | A GUI window (tkinter). A third-party terminal library. A line interface only, which would make alarms and selection hard to see. |
| Every time is time-zone aware. A time typed without an offset is Hong Kong Time (`Asia/Hong_Kong`). Comparisons use instants. | The same PIM File then means the same instants on every machine. HKT has no daylight saving. | The machine's local zone. Requiring an offset on every input. |

## 5.2 Structure

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| Three top-level packages, `model`, `view`, and `controller`, plus `pim.py` as the composition root (Section 2.2). | The brief requires a package named exactly `model`, and the other components must be easy to identify. | A nested `pim.model`, which is not the required name. View and controller code inside `pim.py`. |
| `model` is one deep module behind a small interface: `PIM`, `parse_criterion`, and the criterion classes. | Validation, matching, and the JSON codec stay inside, so every rule sits in one place and is unit-tested without the screen. | Loose procedural functions. A service class over plain records. A `Storage` interface with a single implementation. |
| The View owns an in-process event loop with a 500 ms tick. The model never reads the clock: `now` is passed in (Section 2.2). | Alarm Alerts appear while the user is idle, without a second process. Alarm tests control time exactly. | Blocking on `input()`. A background process or operating-system notifications. |

## 5.3 Data and rules

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| A PIM File is UTF-8 JSON (`"format": "pim/v1"`). `save` appends `.pim` if it is missing, and `load` rejects any other extension. | The brief fixes only the `.pim` extension. JSON is in the standard library, readable, and easy to test (SRS FR-31). | `pickle`: opaque, and unsafe to load. YAML: needs a third-party parser. A custom text format: extra parser work. |
| A system-assigned integer Id is the only identity. It is stored in the file and never reused. | Row numbers change with every search. Descriptions and Contact names repeat, for example a weekly class. | A unique label chosen by the user. Selecting by row position alone. |
| A PIR's type cannot change. | US6 modifies a PIR's data. The fields of different types do not map onto each other. | Converting a PIR in place. The user deletes it and creates one of the new type. |
| An Event has zero or more alarms. Each is *Relative* (at the start or a whole number of units before it) or *Absolute* (a fixed instant), as in the iCalendar `TRIGGER`. | Several reminders per event is the standard model. Relative alarms move with the start; absolute ones do not. | Exactly one alarm. Relative alarms after the start, which an absolute alarm already covers. The `.ics` file format. |
| No recurring events. | Appendix B does not ask for them. A series needs a second life cycle (one occurrence or the whole series) and earns no credit. | Repeat rules (RRULE). A weekly class is several Events. |
| `contains` is a substring test after `str.casefold()` on both sides. | US7 asks for a substring test. Ignoring case is kinder to the user, and case folding does not depend on the locale. | Fuzzy matching. Locale-dependent comparison. |
| A failed command changes nothing and shows one English status line. | Invalid input is normal at a command line. The model validates a copy (`modify`) or parses the whole file (`load`) before it replaces anything, so each error requirement is testable (SRS NFR-4). | Partial updates. Printing a traceback or ending the program. |

## 5.4 Interaction

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| Create and modify ask for one field at a time. Search takes one criterion line (grammar in SRS FR-16). | Prompts need no syntax to remember. A criterion must be exact to be testable, especially `&&`, `\|\|`, `!`, and time comparisons. | All fields on one command line. A menu-driven query builder. |
| Commands are verbs (`create`, `search`, `modify`, `print`, `delete`, `save`, `load`, …). On a terminal, single keys such as `c`, `/`, `w`, `W`, and `o` are shortcuts for the same verbs. | The verbs map one-to-one onto Appendix B, so the SRS, the user manual, and the screen name one list. | Numbered menus. A separate key-only command language. |
| On a terminal, the load and save-as prompts open a folder browser listing folders and `.pim` files. `/` or Tab switches to a typed path. | Users expect to pick a location, and a bare `path:` field hid how to open a file. The chosen path goes to the same handler as a typed one, so the `.pim` rule, the overwrite question, and unsaved-changes handling stay in one place. | A Finder dialog through `osascript`, or tkinter's file dialog: both are GUI windows. |

## 5.5 Testing

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| `unittest` in three layers: unit, integration, and end-to-end. Model unit tests cover 100 % of `model/` lines. A `hooks/pre-commit` script refuses a commit unless all three layers pass. | The brief grades the model's unit tests. Integration tests and scripted sessions through `Terminal.run()` catch breaks between packages. `coverage_report.py` measures lines with the standard `trace` module, so everything stays in the standard library. | pytest and `coverage.py` (third-party). Testing the model only. |

# 6. Design quality

**Modularity.**

- Each package has one reason to change: the screen (`view`), the command flow (`controller`), or the rules and data (`model`).
- `model` has a small public interface (`PIM` plus the criterion constructors) and hides the JSON codec and the matching logic behind it.
- 100 % of `model` lines are covered by unit tests that never touch the View.

**Efficiency.**

- Search, the alarm check, and save and load are each linear in the number of PIRs.
- With 10,000 PIRs they take 2 ms, 2 ms, 44 ms, and 24 ms on the development Mac (SRS NFR-7).
- The View redraws only when its screen snapshot changes, so the 500 ms tick does not cause flicker.

**Extendibility.**

- *A new criterion* is a new `Criterion` subclass plus one parser branch.
- *A new PIR type* is a `PIR` subclass with its `FIELDS`, plus its registrations: the type name in `TYPE_NAMES` and `pir_class`, one branch in `pir_from_json`, one `PIM.create_*` method, and one entry in the controller's `_CREATE` table. The View's prompts are generated from `FIELDS`, so the View does not change.
- *A new front end* can reuse `App` unchanged.

**Justifiability.** Section 2.1 explains why the system uses MVC, and Section 5 gives the reason and the rejected alternatives for every other choice that is hard to reverse.
