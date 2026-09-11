# Personal Information Management

A single-user terminal PIM that holds, searches, and persists the user's personal information records. Interaction is stdlib-only; the quality bar is a designed terminal UI, not a third-party TUI framework.

## Language

**PIM**:
The system: one Working Collection of PIRs, plus store and load of that collection through a PIM File.
_Avoid_: app, database, manager, tool

**Working Collection**:
The PIRs currently in the PIM. Distinct from any PIM File on disk. Save copies this collection to a file; load replaces it from a file.
_Avoid_: session, memory, database, state

**PIR**:
One personal information record of exactly one type. Identified only by its Id.
_Avoid_: item, entry, object, record (unqualified), note (as a generic synonym)

**Id**:
The unique system-assigned identity of a PIR. Persisted in the PIM File, stable across save/load, not reused after delete.
_Avoid_: index, row number, label, key, name (as identity)

**Note**:
A PIR whose required content is a single body of plain text. No separate title field.
_Avoid_: memo, title+body note

**Task**:
A PIR with a required description and an optional deadline.

**Event**:
A PIR with a required description, a required starting time, and zero or more Alarms.
_Avoid_: meeting, appointment (as type names)

**Alarm**:
A reminder on an Event. Either Relative (at start, or a duration before start — never after) or Absolute (a stored instant). An Event may have several.
_Avoid_: notification, series, trigger (as the user-facing word), recurrence

**Effective Alarm Time**:
The instant compared in search and shown in print. Relative: starting time minus the duration (zero duration = at start). Absolute: the stored instant.

**Contact**:
A PIR with a required name and optional address and mobile number.
_Avoid_: person, friend, address book entry

**Name**:
The Contact's person name. Not unique. Not an identity.
_Avoid_: label, title (as a unique alias), id

**Display Name**:
A derived short string for lists, not stored. Note: first line of the body. Task: description. Event: description. Contact: name. Not unique.
_Avoid_: label, title field, filename

**Alarm Alert**:
An in-app banner shown while the PIM process is running. OVERDUE: Effective Alarm Time ≤ now and not dismissed. SOON: Effective Alarm Time in the next 15 minutes and not dismissed. Dismiss is in-memory only.
_Avoid_: push, daemon, system notification, series

**Bound File**:
The PIM File currently associated with the Working Collection, or none if never saved. Save to the Bound File does not ask again. Load replaces the Working Collection and the Bound File.
_Avoid_: open document (unqualified), path

**Current Result**:
The list of PIRs shown on screen. Starts as the whole Working Collection. A search replaces it with matches. Clearing search restores the whole collection.
_Avoid_: query result (as identity), selection

**Search Criterion**:
A condition that selects PIRs by type and/or field values. Text matching is contains: a substring test after Unicode case fold (`str.casefold`), never fuzzy/edit-distance. Time matching is before, after, or equal on an instant. Conditions combine with and, or, and not, with precedence not > and > or. A time comparison on a missing field is false. `alarm` matches if any of the Event's effective alarm times matches.

Field identifiers: `type`, `text` (Note body), `description`, `name`, `address`, `mobile`, `deadline`, `start`, `alarm`. Type values: `note`, `task`, `event`, `contact`. Unqualified `contains "..."` matches any text field of that PIR.
_Avoid_: filter, query, rule, fuzzy search, label lookup, title

**Hong Kong Time**:
The default timezone when a datetime is entered without a zone. IANA `Asia/Hong_Kong` (HKT, UTC+8, no DST). Comparisons use the absolute instant.
_Avoid_: local time, system time, naive datetime

**PIM File**:
A UTF-8 JSON file with the extension `.pim` that stores a Working Collection.
_Avoid_: database file, save file, dump, export, YAML, pickle
