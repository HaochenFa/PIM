# User manual

A single-user terminal Personal Information Manager. Four PIR types: Note, Task, Event, Contact. Files use the extension `.pim` (UTF-8 JSON). Default timezone is Hong Kong Time (`Asia/Hong_Kong`).

Start: `python pim.py`

On an interactive terminal this opens a full-screen UI (Python's standard `curses` library). Redirected input, tests, or `PIM_NO_CURSES=1` keep a line-oriented layout with the same commands.

## Screen

- Title: bound file or `untitled`, `*` if unsaved; HKT clock on the right
- Alarm sticky: OVERDUE (effective time ≤ now) and SOON (next 15 minutes). `d` dismisses the first one (this process only)
- Current Result table (Id, type, Display Name, time) beside DETAIL of the selection
- Status line, key hints, prompt

On a narrow terminal the list stacks above the detail pane. If the window is smaller than about 60×12, widen it; `q` still quits.

## Keys (full-screen UI)

These run immediately when the prompt is empty (nothing typed, no wizard):

| Key | What it does |
|---|---|
| `↑` `↓` / `j` `k` | Select the previous or next row of Current Result |
| `PgUp` `PgDn` / `Home` `End` | Page, first row, last row |
| `/` | Search: enter one criterion line |
| `c` | Create: choose type, then fields |
| `m` | Modify the selection |
| `p` / `P` | Print the selection / print all of Current Result |
| `x` or `Delete` | Delete the selection (`y`/`n`) |
| `d` | Dismiss the first listed alarm |
| `w` | Save (asks for a path if untitled) |
| `:` | Type a full command (same verbs as below) |
| `?` | Key help overlay |
| `q` | Quit |
| `Esc` | Cancel the current prompt or typed command. Does not drop unsaved changes |

While a wizard is asking for a field, type the value and press Enter. Empty Enter skips an optional field, or keeps a field during modify.

## Commands

| Command | What it does |
|---|---|
| `create` / `create note\|task\|event\|contact` | Prompt for fields. Empty enter skips an optional field. After an Event start, you may add several alarms. |
| `search <criterion>` | Replace Current Result with matches. `search` alone then asks for the criterion. |
| `clear` | Show the whole collection again |
| `<n>` | Select row n of Current Result (not an identity) |
| `id <n>` | Select by Id |
| `modify` | Prompt for fields of the selection. Empty enter keeps a field. `none` clears an optional field. |
| `print` | Print every field of the selection (Event alarms include kind and effective time) |
| `print all` | Print every PIR in **Current Result** |
| `delete` | Confirm `y`/`n` |
| `save` / `save as <path>` | Store the collection. `.pim` is appended if omitted. Overwriting another file asks. |
| `load <path>` | Replace the collection. Non-`.pim` paths are rejected. Unsaved changes ask save / discard / cancel. |
| `dismiss` | Hide the first listed alarm for this process (not written to the file) |
| `help` | Command list |
| `quit` | Unsaved changes ask save / discard / cancel. Ctrl-C and closing input (Ctrl-D) are the same as quit; they do not silently drop unsaved changes. |

## Search criterion

```
type = note|task|event|contact
text|description|name|address|mobile contains "..."
contains "..."
deadline|start|alarm  < | > | =  <datetime>
&&  ||  !   and parentheses
```

`contains` is a case-insensitive substring (`str.casefold`), not fuzzy match. A time comparison on a missing field is false. `alarm` matches if **any** effective alarm time matches. Precedence: `!` then `&&` then `||`.

Datetimes: ISO 8601, or `YYYY-MM-DD HH:MM`. If you omit a zone, Hong Kong Time is used.

## Alarms (Event)

Relative: at start (`amount` 0) or N minutes/hours/days/weeks **before** start. Absolute: a specific instant. Changing start moves relative effective times only.

## Errors

Invalid input does not change your data, does not print a traceback, and does not exit. The status line names the problem (missing field, bad Id, bad datetime, bad search syntax, wrong extension, no selection, attempt to change type).

## Examples

Full-screen keys (prompt empty):

```
c
note
Shopping: Milk
/ type = event && description contains "COMP"
↓
m
```

The same session as typed commands (`:` first in the full-screen UI, or any line-oriented session):

```
create note
search type = event && description contains "COMP"
id 4
modify
print all
save as demo.pim
```
