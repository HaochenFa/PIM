# Product Description and Decisions

Product scope for the COMP3211 command-line Personal Information Management (PIM) system. Domain terms are defined in `CONTEXT.md`. Irreversible choices are recorded in `docs/adr/`.

This document covers interaction and semantics the assignment leaves to the group. It does **not** add product capability beyond Appendix B.

---

## 1. What the product is

The PIM is a **single-user, single-process, in-terminal** personal information manager. The user creates, searches, modifies, deletes, and prints four kinds of PIR in one Working Collection, stores that collection in a file with the extension `.pim`, and loads it back.

It is not a multi-user system, a network service, a GUI, or a calendar daemon. An Alarm is data that can be searched, printed, and surfaced as an in-process banner. The PIM does not call OS notifications and does not start a second process.

## 2. Scope

### In

| Capability | User stories |
|---|---|
| Four PIR types: Note, Task, Event, Contact | US1–US5 |
| Modify fields of an existing PIR (type is immutable) | US6 |
| Search by type, fields, contains, time comparison, `&&` `||` `!` | US7 |
| Print one PIR or every PIR in the current list | US8 |
| Delete a specified PIR | US9 |
| Store to / load from `.pim` | US10–US11 |
| In-process Alarm Alert (overdue + due within 15 minutes) | HCI derived from US4 alarms, not a new story |

### Explicitly out (extra features, no extra credit)

- GUI, third-party TUI (Textual / Rich / Click); stdlib `curses` on a TTY is the designed terminal (ADR-0018)
- Any pip dependency; Python standard library only
- Networking, multi-user, sync
- Recurring events / Event Series / RRULE
- Links between PIRs (an Event does not reference a Contact)
- Unique labels, a global title field, fuzzy (edit-distance) search
- Changing a PIR’s type, a background daemon, OS notifications, snooze / postpone

## 3. Domain objects

### PIR and Id

Each PIR has exactly one type. The only identity is a system-assigned integer **Id**: monotonic at creation, persisted in the PIM File, never reused after delete. Display Name, list row numbers, and a Contact’s Name are not identity.

Display Name is derived and not stored: Note = first line of the body; Task/Event = description; Contact = name. Duplicates are allowed.

### Types and fields

| Type | Required | Optional | Search field names |
|---|---|---|---|
| Note | `text` (body) | — | `text` |
| Task | `description` | `deadline` | `description`, `deadline` |
| Event | `description`, `start` | `alarms` (0..n) | `description`, `start`, `alarm` |
| Contact | `name` | `address`, `mobile` | `name`, `address`, `mobile` |

Empty or whitespace-only strings count as missing. Missing required fields make create/modify fail; the Working Collection is unchanged.

Type cannot change after creation. To obtain another type, delete and create (new Id).

### Time

- Every timestamp is a timezone-aware instant.
- If the user omits a zone, the default is **Hong Kong Time** (IANA `Asia/Hong_Kong`, UTC+8, no DST).
- Storage and comparison use ISO 8601.
- Granularity is one minute.
- `<` `>` `=` compare instants, not clock faces.

### Alarm (Event only)

An Event may have zero or more Alarms. Each alarm is either:

- **Relative**: relative to `start`, only “at start” or “N minutes/hours/days/weeks before”; or
- **Absolute**: a standalone instant.

Semantics follow iCal `VALARM`/`TRIGGER` (DURATION or DATE-TIME). The file remains JSON; the product does not export `.ics`.

**Effective Alarm Time**: Relative = `start − duration` (duration 0 = at start); Absolute = the stored instant. Changing `start` recomputes Relative alarms only. Search `alarm < T` means **any** effective instant satisfies T.

While the process is running:

- OVERDUE: effective instant ≤ now, and not dismissed
- SOON: effective instant in the next 15 minutes, and not dismissed

Dismiss lives in memory only and is not written to the `.pim` file. No OS notification. No second process.

### Search

The user enters one criterion. Grammar:

```
type = note|task|event|contact
text|description|name|address|mobile contains "..."
contains "..."                  # any text field of that PIR
deadline|start|alarm  < | > | =  <ISO datetime>
&&  ||  !   and parentheses
precedence: ! > && > ||
```

Rules:

- contains: substring after `str.casefold()` on both sides (not locale, not fuzzy match).
- A time comparison on a missing field is false (a Task with no deadline does not match `deadline < T`).
- Syntax error: report it; Current Result is unchanged.
- Successful search: Current Result becomes the hit list. Clearing search restores the whole collection.

### Persistence

- A Working Collection has at most one Bound File.
- The extension must be `.pim`. Save appends it if omitted. Load rejects any other extension.
- The user chooses where the file goes, or which file to open, with a folder browser on the TTY, or by typing its path (always possible, and the only way in the line UI). A typed path may be absolute, start with `~` for the home folder, or be relative to the folder the PIM was started from. After a save or load, the status line names the absolute path. There is no GUI file dialog (ADR-0019).
- Bytes are UTF-8 JSON (schema in the architecture document).
- `save` writes the Bound File without confirmation. `save as` onto an existing path requires confirmation. With no Bound File, `save` is `save as`.
- `load` replaces the Working Collection and the Bound File. If the collection is dirty, the user must save / discard / cancel; modifications must not be dropped silently. The same rule applies on quit.

## 4. Interaction

Designed terminal UI (stdlib `curses` on an interactive TTY; line-oriented layout when stdin/stdout is not a TTY or `PIM_NO_CURSES` is set; no third-party libraries):

1. Title line: Bound File or untitled, dirty flag, HKT clock
2. Alarm Alert banner (dismissible)
3. Current Result table: Id / type pin / Display Name / relevant time
4. Detail of the selection
5. Menu + prompt (selectors and a calendar for closed answers; a folder browser for load and save-as paths; one criterion line for search)

Letter keys and arrows are accelerators for the same verb commands. They do not replace prompted create/modify or the criterion grammar.

| Intent | How |
|---|---|
| Create US1–US5 | Choose type, then prompt field by field; empty enter on an optional field omits it; after each Event alarm, ask whether to add another |
| Search US7 | Enter one full criterion line |
| Select | Id, or a row number of the current list (row numbers are not identity) |
| Modify US6 | Select first; empty enter keeps that field |
| Print US8 | Print the selection; `print all` prints every PIR in **Current Result** |
| Delete US9 | Select first, confirm y/n |
| Store/load US10–US11 | `save` / `save as` / `load` (keys `w` / `W` / `o`); when a path is needed, the TTY opens a folder browser and the line UI asks for a typed path |

Invalid input: **commands fail atomically** — Working Collection unchanged, no traceback, process stays up, one specific English error on the status line. Cases: unknown command, missing required field, empty body, bad Id, bad datetime, bad search syntax, not `.pim`, missing path, load while dirty, delete/modify/print-one with no selection, attempt to change type.

## 5. Locked decisions (summary)

| ID | Decision |
|---|---|
| ADR-0001 | Python, not Java |
| ADR-0002 | `model` is a deep OO module: small `PIM` interface + PIR hierarchy + composite Criterion |
| ADR-0003 | `.pim` contains UTF-8 JSON |
| ADR-0004 | Standard library only; designed terminal, not a GUI / Textual (curses clause → ADR-0018) |
| ADR-0005 | Default timezone HKT |
| ADR-0006 | The only unique identity is the system Id |
| ADR-0007 | Alarms follow iCal TRIGGER semantics (relative or absolute, several allowed) |
| ADR-0008 | contains uses Unicode casefold |
| ADR-0009 | No recurrence |
| ADR-0010 | View event loop, 500ms tick, redraw on change (TTY: curses timeout; else stdin thread) |
| ADR-0011 | Top-level packages `model/` `view/` `controller/` + `pim.py` |
| ADR-0012 | PIR type is immutable after creation |
| ADR-0013 | Prompted create/modify; criterion line for search |
| ADR-0014 | A failed command does not change data |
| ADR-0015 | `.pim` extension is enforced |
| ADR-0018 | Stdlib curses on a TTY; line UI for scripts and tests |
| ADR-0019 | Folder browser for load / save-as paths on the TTY; typed paths stay; no GUI dialog |

Glossary: `CONTEXT.md`. Do not use Name as a title, Label as identity, or Note as a field name.
