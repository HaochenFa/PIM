---
title: "Software Requirements Specification — Personal Information Management (PIM) System"
subtitle: "COMP3211 Software Engineering, Fall 2026 — Group Project"
date: "Version 1.0 draft, 23 September 2026"
---

> **Derived document.** The normative sources are `docs/PRODUCT.md` and `docs/ACCEPTANCE.md` in the source tree. If this SRS and those files disagree, fix those files first, then regenerate this document.

# 1. Preface

## 1.1 Readers

This specification is for three groups of readers:

- The course instructor and teaching assistants, who grade the system against Appendix B of the project description.
- The group members who design, implement, and test the system.
- Anyone who later maintains or tests the system.

Readers are expected to know basic software-engineering terms. They do not need to know Python.

## 1.2 Version history

| Version | Date | Change |
|---|---|---|
| 1.0 draft | 23 Sep 2026 | First complete draft. It covers user stories US1–US11, the in-process Alarm Alert, and the non-functional constraints of the brief. |

## 1.3 Conventions

- **Requirement ids.** Functional requirements are `FR-n` and non-functional requirements are `NFR-n`.
- **"shall".** Every requirement uses *shall* and can be checked by a test or an inspection. The *Verification* line names how.
- **Rationale.** Italic text under a requirement explains why it exists. The rationale is not itself a requirement.
- **Commands and input.** Terms in `monospace` are commands, field names, or literal input that the user types.

# 2. Introduction

## 2.1 Purpose of the system

The PIM is a **single-user, command-line personal information manager**. One user runs it in a terminal on one computer. The user can:

- create four kinds of personal information record (PIR): notes, tasks, events, and contacts;
- modify, search, print, and delete PIRs;
- store PIRs in a file with the extension `.pim` and load them again later.

All information the user cares about is kept in one place, and it survives between runs of the program (US1).

## 2.2 Scope

**In scope:** everything that user stories US1–US11 of Appendix B require, plus one derived feature. While the program runs, it shows an **Alarm Alert** banner for Event alarms that are overdue or due within 15 minutes. This makes the alarms of US4 useful to the user; it is not a new user story.

**Out of scope:** the brief gives no credit for extra features, so the system deliberately does not provide:

- a graphical user interface, or any third-party terminal library;
- networking, several users, or synchronisation;
- recurring events;
- links between PIRs;
- unique labels or titles, and fuzzy (edit-distance) search;
- changing the type of an existing PIR;
- operating-system notifications, background processes, and snooze.

## 2.3 How the system fits its environment

The system is one Python 3 process that uses only the standard library. The user types commands in a terminal:

- On an interactive terminal (TTY), the system shows a full-screen text interface built with the standard `curses` module.
- When input or output is redirected, as in automated tests, it uses a plain line-by-line interface.

The system reads and writes `.pim` files on the local file system. It has no other external interfaces.

# 3. Glossary

| Term | Meaning |
|---|---|
| PIM | The system: one Working Collection of PIRs, with store and load through a PIM File. |
| PIR | Personal Information Record. It has exactly one type: Note, Task, Event, or Contact. |
| Id | The unique, system-assigned integer identity of a PIR. It is stored in the PIM File, stays the same across save and load, and is never reused after a delete. |
| Working Collection | The PIRs currently in the running program, as distinct from any file on disk. |
| Note | A PIR whose only content is a required plain-text body, the field `text`. It has no separate title. |
| Task | A PIR with a required `description` and an optional `deadline`. |
| Event | A PIR with a required `description`, a required starting time `start`, and zero or more Alarms. |
| Contact | A PIR with a required `name` and an optional `address` and `mobile` number. |
| Name | The person name of a Contact. It is not unique and is not an identity. |
| Alarm | A reminder attached to an Event. It is either *Relative* (at start, or a duration before start) or *Absolute* (a fixed instant). |
| Effective Alarm Time | The instant an Alarm fires. For a Relative alarm it is `start` minus the duration; for an Absolute alarm it is the stored instant. |
| Display Name | A short label derived for list views and never stored. For a Note it is the first line of the body; for a Task or Event, the description; for a Contact, the name. |
| Current Result | The list of PIRs on screen. At first it is the whole Working Collection; a search replaces it with the matches. |
| Selection | The one PIR, chosen by Id or by row of the Current Result, that `modify`, `print`, and `delete` act on. |
| Search Criterion | A condition over PIR type and field values, written as one line (see FR-16). |
| Bound File | The `.pim` file last saved or loaded, or none. |
| Dirty | The state in which the Working Collection has changes not yet saved. |
| HKT | Hong Kong Time, IANA zone `Asia/Hong_Kong` (UTC+8, no daylight saving). It is the default time zone. |
| PIM File | A UTF-8 JSON file with the extension `.pim` that stores a Working Collection. |
| Status line | The one-line message area where the system reports the outcome of every command. |

# 4. User requirements definition

The system shall support the following user stories, copied from Appendix B of the project description. Each story is refined into system requirements in Section 6.

| Id | User story | Refined by |
|---|---|---|
| US1 | As a user, I want to create different types of PIRs in the PIM so that all the information I care about can be managed in a single location. | FR-1 – FR-3, FR-10, FR-11 |
| US2 | As a user, I want to create new plain texts as PIRs so that I can use the PIM to take quick notes. | FR-4 |
| US3 | As a user, I want to create new tasks with the corresponding descriptions and deadlines as PIRs so that I can use the PIM to manage my to-dos. | FR-5 |
| US4 | As a user, I want to create new events with the corresponding descriptions, starting times, and alarms as PIRs so that I can use the PIM to manage my schedule. | FR-6 – FR-8, FR-40 – FR-42 |
| US5 | As a user, I want to create new contacts with the corresponding names, addresses, and mobile numbers as PIRs so that I can use the PIM to manage my contacts. | FR-9 |
| US6 | As a user, I want to modify the data in existing PIRs so that I can keep the PIRs up to date. | FR-12 – FR-15 |
| US7 | As a user, I want to search for PIRs based on criteria concerning their types and the data stored in their fields (contains, <, >, =, &&, \|\|, !). | FR-16 – FR-23 |
| US8 | As a user, I want to print out detailed information about a specific PIR or all PIRs. | FR-24 – FR-26 |
| US9 | As a user, I want to delete a specified PIR. | FR-27, FR-28 |
| US10 | As a user, I want to store the PIRs in a file with the extension ".pim" so that I can access them using the PIM in the future. | FR-29 – FR-33 |
| US11 | As a user, I want to load the PIRs from a file with the extension ".pim" so that I can continue working with the PIRs I stored earlier. | FR-34 – FR-37 |

# 5. System architecture

The system follows the **Model–View–Controller** (MVC) pattern, with one Python package per component. The design document explains the architecture in full; this section only names the parts so that the requirements can refer to them.

- **`model`** holds everything about the data:
  - the Working Collection (class `PIM`) and the four PIR types;
  - alarms;
  - the search-criterion parser and matcher;
  - reading and writing the PIM File.

  It has no user interface and imports neither `view` nor `controller`, so it can be unit-tested on its own.
- **`controller`** turns one completed user action into calls on the model. It keeps the Current Result and the Selection, and it maps every failure to one status-line message.
- **`view`** draws the terminal screen, reads keys and lines, runs the event loop, and shows Alarm Alerts. It calls the controller only.
- **`pim.py`** is the composition root. It creates `PIM()`, then `App(pim)`, then `Terminal(app)`, and runs the terminal.

# 6. System requirements specification

## 6.1 Creating PIRs (US1–US5)

**FR-1** The system shall support exactly four PIR types: Note, Task, Event, and Contact. The command `create note|task|event|contact` shall start creating a PIR of the named type. `create` without a type shall first ask for the type.
*Verification:* unit tests for each type; e2e create scripts.

**FR-2** When a PIR is created, the system shall give it an Id equal to the next Id of the Working Collection and then increase the next Id by one. The first Id of a new collection shall be 1.
*Verification:* a unit test creates four PIRs and checks the Ids 1–4.

**FR-3** The system shall ask for the fields of a new PIR one prompt at a time. On an optional field, an empty answer shall leave the field unset.
*Rationale: prompted entry needs no syntax to remember, and every field is named on the screen.*
*Verification:* e2e create scripts.

**FR-4 (Note)** A Note shall have one required field, `text`. The system shall reject a Note whose text is empty or whitespace only. The Display Name of a Note shall be the first line of its text.
*Verification:* unit tests for Note.

**FR-5 (Task)** A Task shall have a required `description` and an optional `deadline`.
*Rationale for the optional deadline: many to-dos have no date, and forcing an invented date would make time searches such as `deadline < T` give false results. Where a deadline is given, US3 is fully met.*
*Verification:* unit tests for Task.

**FR-6 (Event)** An Event shall have a required `description`, a required `start`, and zero or more Alarms. After each alarm, the system shall ask whether to add another.
*Rationale for zero alarms: not every event needs a reminder. Any number of alarms, of either kind, can be added.*
*Verification:* unit tests for Event.

**FR-7 (Alarm kinds)** Each Alarm shall be one of:

- *Relative*: a non-negative whole number `amount` and a `unit` of `minute`, `hour`, `day`, or `week`. The alarm fires that long **before** `start`; an amount of 0 means *at start*. A negative amount (after start) shall be rejected, and so shall an amount that is not a whole number.
- *Absolute*: a stored instant, independent of `start`.

*Verification:* unit tests for alarms.

**FR-8 (Alarm range)** The system shall reject an Event if any Effective Alarm Time falls outside the representable date range (years 1–9999). An example is 999999999 weeks before start. The status message shall be `alarm time is out of range`.
*Verification:* unit test and e2e test "overflowing relative alarm".

**FR-9 (Contact)** A Contact shall have a required `name` and an optional `address` and `mobile`. Two Contacts may have the same name.
*Verification:* unit tests for Contact.

**FR-10 (Missing values)** An empty or whitespace-only answer shall count as a missing value. Leading and trailing spaces shall be removed from stored text. If a required field is missing, the create shall fail with a message naming the field, for example `description is required`.
*Verification:* unit tests for each type.

**FR-11 (Date and time input)** The system shall accept a date-time as ISO 8601 or as `YYYY-MM-DD HH:MM`, with or without a time-zone offset:

- A value without an offset shall be taken as Hong Kong Time.
- Seconds shall be dropped, because the system works to the minute.
- A value that cannot be parsed shall be rejected with `invalid datetime: <value>`.
- A value that cannot be expressed in both HKT and UTC within years 1–9999, such as `9999-12-31T23:59-10:00` or `0001-01-01 00:10`, shall be rejected with `datetime out of range`, so that every saved value can be loaded back (FR-35).

On a TTY, the full-screen interface shall also offer a calendar picker.
*Verification:* unit tests for date-time parsing.

## 6.2 Modifying PIRs (US6)

**FR-12** The command `modify` shall ask for each field of the selected PIR, and show its current value. For each field:

- an empty answer shall keep the current value;
- the answer `none` shall clear an optional field;
- for an Event, the user shall be asked whether to replace the alarm list.

*Verification:* e2e modify scripts.

**FR-13** Modifying a PIR shall never change its Id or its type. An attempt to change the type shall fail with `PIR type cannot be changed`.
*Rationale: the Id is the only identity (ADR-0006). A different type is a different record, so the user deletes the PIR and creates a new one.*
*Verification:* unit test "modify cannot change type".

**FR-14** When the `start` of an Event changes, the Effective Alarm Times of its Relative alarms shall move with it, and those of its Absolute alarms shall not.
*Verification:* unit test "relative effective times move with start".

**FR-15** A modify that fails validation shall leave the PIR exactly as it was. A modify that changes nothing shall not mark the collection dirty.
*Verification:* unit tests for modify.

## 6.3 Searching (US7)

**FR-16 (Criterion grammar)** The command `search <criterion>` shall accept one criterion line with this grammar (`!` binds tightest, then `&&`, then `||`):

```
criterion  := or
or         := and ( "||" and )*
and        := not ( "&&" not )*
not        := "!" not | primary
primary    := "(" criterion ")" | atom
atom       := "type" "=" ("note"|"task"|"event"|"contact")
            | textfield "contains" STRING
            | "contains" STRING
            | timefield ("<"|">"|"=") DATETIME
textfield  := "text" | "description" | "name" | "address" | "mobile"
timefield  := "deadline" | "start" | "alarm"
STRING     := '"' characters '"'      (\" and \\ escape)
```

*Verification:* unit tests for the parser.

**FR-17 (Type)** `type = T` shall match exactly the PIRs of type T.

**FR-18 (Contains)** `f contains "s"` shall match a PIR that has text field `f` when `s`, after Unicode case folding, is a substring of the folded field value. The match shall not be fuzzy and shall not depend on locale. A PIR without field `f` shall not match.

**FR-19 (Unqualified contains)** `contains "s"` shall match a PIR when any of its text fields contains `s` in the sense of FR-18.

**FR-20 (Time comparison)** `f < T`, `f > T`, and `f = T` shall compare instants, not clock faces, to the minute. So `start = 2026-09-14 18:30` equals `start = 2026-09-14T10:30Z`. A comparison on a field the PIR does not have, or has not set (a Task with no deadline), shall be false. For `alarm`, the Event shall match if **any** of its Effective Alarm Times satisfies the comparison.

**FR-21 (Logic)** `A && B`, `A || B`, `!A`, and parentheses shall combine criteria with their usual Boolean meaning and the precedence of FR-16.

**FR-22 (Result)** A successful search shall replace the Current Result with the matching PIRs in increasing Id order, select the first match, and report `<n> match(es)`. The command `clear` shall restore the Current Result to the whole Working Collection.

**FR-23 (Syntax error)** A criterion that does not follow FR-16 shall be reported as `search syntax error: <reason>`, and the Current Result shall stay unchanged. In the full-screen interface, the typed criterion shall stay in the input field so that it can be corrected.

*Verification of FR-17 – FR-23:* unit tests for search on the fixture of ACCEPTANCE §4; e2e search scripts.

## 6.4 Printing (US8)

**FR-24** The command `print` shall print every field of the selected PIR with its Id and type. For an Event, it shall print each Alarm's kind and its Effective Alarm Time.

**FR-25** The command `print all` shall print every field of every PIR in the **Current Result**, in list order. When no search is active (at start-up, after `clear`, or after `load`), the Current Result is the whole Working Collection, so `print all` prints all PIRs.
*Rationale: US8 asks to print "all PIRs". Printing the Current Result also lets the user print "all PIRs that match a search", which is the more useful reading. The user gets every PIR by running `clear` first.*

**FR-26** `print`, `modify`, and `delete` with no Selection shall fail with `no PIR selected`.

*Verification of FR-24 – FR-26:* controller unit tests; e2e print scripts.

## 6.5 Deleting (US9)

**FR-27** The command `delete` shall ask for confirmation (`y`/`n`) and then remove the selected PIR. `n` shall leave the collection unchanged.

**FR-28** An Id shall never be reused, not even after its PIR is deleted, or after a save and a load.
*Verification of FR-27 – FR-28:* unit test "Id not reused after delete and save/load".

## 6.6 Storing (US10)

**FR-29** `save as <path>` shall write the Working Collection to `<path>`, appending `.pim` when the path does not already end in `.pim`. The path then becomes the Bound File. `save` shall write to the Bound File without asking, or behave as `save as` when there is none. The user chooses the folder by typing the path: it may be absolute, begin with `~` for the home folder, or be relative to the folder the system was started from. This typed path is the command-line counterpart of a file dialog. After a successful save, the status line shall name the absolute path that was written.

**FR-30** If `save as` would replace an existing file that is not the Bound File, the system shall ask for confirmation.

**FR-31** A PIM File shall be UTF-8 JSON with `"format": "pim/v1"`, the next Id, and every PIR with its Id, type, and fields. For an Event, each Alarm shall be stored with its kind.

**FR-32** The system shall write the file atomically: it writes a temporary file in the same folder, then replaces the target. A failed write shall leave any earlier file intact. If the operating system refuses the write, the system shall report `cannot save <file>.pim: <reason>`, and the collection shall stay dirty.

**FR-33** An empty path, or a path that is only `.pim`, shall be rejected with `file name is required`.

*Verification of FR-29 – FR-33:* unit tests for persistence; controller unit test for OS errors.

## 6.7 Loading (US11)

**FR-34** `load <path>` shall accept only a path ending in `.pim`; any other path shall be rejected before the file is read. A successful load shall replace the Working Collection, the next Id, and the Bound File, and shall clear any search. `<path>` takes the same forms as in FR-29, and the status line shall name the absolute path that was read.

**FR-35** A successful save followed by a load shall give back the same PIRs with the same Ids, types, fields, alarm kinds, and Effective Alarm Times.

**FR-36** A file that is missing, unreadable, not UTF-8, not JSON, not `pim/v1`, or that holds an invalid PIR shall be rejected with `not a PIM file: <reason>`, and the Working Collection shall stay unchanged. Invalid PIRs include:

- a missing required field;
- a duplicate or non-positive Id, or an Id that is not an integer;
- an alarm list that is not a list;
- an alarm out of range.

**FR-37** If the collection is dirty, `load` and `quit` shall first ask the user to *save*, *discard*, or *cancel*. Cancel shall change nothing. End of input (Ctrl-D) and interrupt (Ctrl-C) shall follow the same rule as `quit`.
*Verification of FR-34 – FR-37:* unit and e2e persistence tests.

## 6.8 User interface

**FR-38** The system shall accept these commands:

- `create [type]`, `search [criterion]`, `clear`
- a row number `<n>`, and `id <n>`
- `modify`, `print`, `print all`, `delete`
- `save`, `save as <path>`, `load <path>`
- `dismiss`, `help`, `quit`

An unknown command shall be reported as an error and change nothing. On a TTY, single-key accelerators (for example `c` create, `/` search, `w` save, `W` save as, `o` load) shall run the same commands.

**FR-39** The screen shall show:

- a title line: the Bound File or "untitled", a dirty mark, and the HKT clock;
- the Alarm Alert banner;
- the Current Result table: Id, type, Display Name, and deadline or start;
- the details of the Selection;
- the status line.

A row number shall select by position in the Current Result and is not an identity.

## 6.9 Alarm Alerts (derived from US4)

**FR-40** While the program runs, it shall show an Alarm Alert for every alarm that is OVERDUE (Effective Alarm Time ≤ now) or SOON (Effective Alarm Time within the next 15 minutes). The alert shall name the Event and the time.

**FR-41** The banner shall update within 500 ms of an alarm becoming due, even when the user types nothing.

**FR-42** The command `dismiss` shall hide an alert for the rest of the process. Dismissals shall not be written to the PIM File, and the system shall not use operating-system notifications or a second process.

*Verification of FR-40 – FR-42:* unit tests for `due_alarms` with an injected `now`; e2e alert scripts.

## 6.10 Non-functional requirements

**NFR-1 (Standard library)** The implementation shall use only the Python 3 standard library.
*Verification:* inspect all imports.

**NFR-2 (Platform)** The system shall run on macOS with Python 3.12 or newer, in Terminal or iTerm. The developer manual shall describe this platform only.

**NFR-3 (Structure)** All model code shall be in a package named `model`, which shall not import `view` or `controller`. The other components shall be in `view` and `controller`.
*Verification:* inspect imports.

**NFR-4 (Reliability)** Invalid input or a failed command shall not change the Working Collection, shall not print a traceback, and shall not end the process. The system shall report exactly one English message on the status line. An unexpected internal error in a command shall be reported as `command failed`, and the session shall continue.
*Verification:* unit, integration, and e2e error tests.

**NFR-5 (Data integrity)** A failed save shall not damage the earlier file, and a failed load shall not change memory (see FR-32 and FR-36). The system shall never silently discard unsaved changes (FR-37).

**NFR-6 (Time)** Every stored time shall carry a time zone. The default zone shall be HKT, and comparisons shall use instants (see FR-11 and FR-20).

**NFR-7 (Performance)** With 10,000 PIRs in the Working Collection, each of the following shall finish within 1 second on the development Mac: a search, the alarm check, a save, and a load.
*Verification:* measured at 7 ms, 2 ms, 42 ms, and 21 ms.

**NFR-8 (Testability)** Every model rule shall be testable through the public `model` interface, without the user interface. Model unit tests shall use `unittest`, run automatically, pass, and reach 100 % line coverage of `model/`.
*Verification:* `python3 -m unittest`; `python3 coverage_report.py`.

**NFR-9 (Usability)** Prompts, messages, and manuals shall be in English. Each error message shall say what went wrong, and shall name the field or value at fault when there is one (for example `description is required`, `no PIR with Id 9`).

**NFR-10 (Scope)** The system shall not include the out-of-scope features listed in Section 2.2.
