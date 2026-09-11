# User manual

A single-user terminal Personal Information Manager. Four PIR types: Note, Task, Event, Contact. Files use the extension `.pim` (UTF-8 JSON). Default timezone is Hong Kong Time (`Asia/Hong_Kong`).

Start: `python pim.py`

## Screen

- Title: bound file or `untitled`, `*` if unsaved
- ALARMS: OVERDUE (effective time ≤ now) and SOON (next 15 minutes)
- Current Result table (Id, type, Display Name, time)
- DETAIL of the selection
- Status line, command list, prompt

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
| `quit` | Unsaved changes ask save / discard / cancel. Closing input (Ctrl-D) is the same as quit; it does not silently drop unsaved changes. |

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

```
create note
search type = event && description contains "COMP"
id 4
modify
print all
save as demo.pim
```
