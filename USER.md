# User manual

A single-user terminal Personal Information Manager. Four PIR types: Note, Task, Event, Contact. Files use the extension `.pim` (UTF-8 JSON). Default timezone is Hong Kong Time (`Asia/Hong_Kong`).

Start: `python pim.py`

On an interactive terminal this opens a full-screen UI (Python's standard `curses` library). Redirected input, tests, or `PIM_NO_CURSES=1` keep a line-oriented layout with the same commands.

## Screen

Each region is a widget with its own title:

- Title bar: bound file or `untitled`, `*` if unsaved; HKT clock
- Alarms: OVERDUE (effective time ≤ now) and SOON (next 15 minutes). `d` dismisses the first one (this process only)
- Current Result (left): the list you search and select
- Detail (right): the selected PIR
- Composer (bottom): idle hints, a **selector**, or a labelled field

On a narrow terminal the list stacks above the detail pane. If the window is smaller than about 60×12, widen it; `q` still quits.

## Selectors (full-screen UI)

When the answer is one of a few values, the composer becomes a selector. You do **not** type the word.

| Situation | Options | How |
|---|---|---|
| Create | Note · Task · Event · Contact | `←` `→`, or `1`–`4`, or `n` `t` `e` `c`, then Enter. A letter confirms immediately. |
| Delete, overwrite, add/replace alarms | Yes · No | Default is **No**. `y` / `n` or arrows + Enter. |
| Alarm kind | Relative · Absolute | `r` / `a` |
| Alarm unit | Minute · Hour · Day · Week | `m` `h` `d` `w` |
| Unsaved changes | Save · Discard · Cancel | Default is **Cancel**. `s` / `d` / `c` |

Free text (note body, names, search criterion, file path) still uses a labelled field. Empty Enter skips an optional field, or keeps a field during modify.

## Date and time (full-screen UI)

Event **start**, Task **deadline**, and an **absolute alarm** open a calendar, not a blank to type into. This matches ordinary calendar apps:

- Left: a month grid, week starting Monday
- Right: times in 15-minute steps (Hong Kong Time)
- The bar under the grid shows what you will save, e.g. `Tue 15 September 2026  18:30  HKT`

| Key | What it does |
|---|---|
| `←` `→` `↑` `↓` | Move by day or week (date) / 15 minutes or 1 hour (time) |
| `Tab` | Switch between the grid and the time list |
| `[` `]` | Previous / next month |
| `t` | Jump to today |
| `+` `-` | Nudge one minute |
| `n` | Skip an optional deadline (or type `none` in the line UI) |
| `Enter` | Use the highlighted date and time |
| `Esc` | Cancel |

You do not type ISO 8601. The line-oriented UI (tests, redirected input) still accepts `YYYY-MM-DD HH:MM` or a full ISO instant; the prompt names that format and Hong Kong Time.

## Keys (full-screen UI)

These run immediately when the prompt is empty (nothing typed, no wizard):

| Key | What it does |
|---|---|
| `↑` `↓` / `j` `k` | Select the previous or next row of Current Result |
| `PgUp` `PgDn` / `Home` `End` | Page, first row, last row |
| `/` | Search: enter one criterion line |
| `c` | Create: open the type selector, then fields |
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

Datetimes: in the full-screen UI, pick from the calendar. In the line UI, ISO 8601 or `YYYY-MM-DD HH:MM`. If you omit a zone, Hong Kong Time is used.

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
