# TUI polish: HKT lecture diary

**Status:** implemented on `feat/tui` (2026-09-12). This file is the design record plus what actually landed. The earlier curses plan is `docs/plans/2026-09-11_tui.plan.md` (TTY curses, selectors, calendar). This pass is HCI quality of that View, not a new product.

Appendix B, MVC, prompted create/modify, one criterion line, and stdlib-only stay locked.

---

## Outcome

Shipped as four conventional commits (the eight-commit split in the first draft was collapsed once the View paint, search retry, and alarm-amount selector were one working tree):

1. `docs(adr): accept stdlib curses as the TTY view` — ADR-0018; PRODUCT / ARCHITECTURE / ACCEPTANCE / AGENTS aligned; ADR-0004 “not curses” clause superseded.
2. `feat(controller): give status a kind and remember the criterion line` — `set_status`, `criterion_line`, `search()` → bool, first-hit select.
3. `feat(view): paint an HKT lecture diary and keep a mistyped search` — `theme.py`, diary paint, stamp, pins, card detail, calendar collision fix, CJK caret, chip wrap, curses-only search retry, idle Esc clears filter, relative-alarm amount selector.
4. `docs(PIM): document the diary screen, keys, and search field` — USER.md, DEVELOPER.md, ARCHITECTURE view files.

`python -m unittest` green after each. Line UI / e2e scripts still type the same verbs.

---

## Subject (frontend-design)

- **What:** a COMP3211 student’s personal organiser — Note, Task, Event, Contact — with in-process OVERDUE/SOON.
- **Who:** the student, and a marker watching a four-minute demo.
- **Job of the screen:** keep the Working Collection readable, make the next action obvious, and make an alarm impossible to miss.

World: a **Hong Kong lecture diary** — timetable gutter, ink on a night-study page, a vermilion office chop on overdue items, HKT as a real clock. Not a code editor. Not `htop`. Not a blue-menu ncurses tutorial.

---

## Constraints (do not reopen)

| Locked | Meaning |
|---|---|
| US1–US11, four types, criterion grammar | No new PIR fields, no query builder that replaces the line |
| ADR-0013 prompted create/modify; one criterion line | Wizards stay field-by-field; search still submits one string |
| ADR-0016 verb commands | Keys remain accelerators; `:` still types the same verbs; demo script still types `create note` |
| `model` deep module | No ANSI, curses, or stdin in `model` |
| Stdlib only | `curses` colour pairs; no Rich/Textual/colour libraries |
| Failed commands atomic; dirty load/quit; injected `now` | Unchanged |
| Line UI for tests / non-TTY | E2E still injects stdin; `PIM_NO_CURSES=1` unchanged |

**Still out:** GUI; Textual/Rich/Click; mouse; user-selectable themes; command palette; fuzzy search; snooze; OS notifications; recurrence; PIR links; changing type; a fifth top-level package; custom fonts.

---

## Design system (as built)

### Colour

Loud colour is **only** the alarm stamp. Roles live in `view/theme.py` (not raw pair numbers in `curses_ui.py`).

| Role | 256 | 8-colour fallback | Use |
|---|---|---|---|
| `page` | 253 on 236 | default | Screen fill (`bkgd` when 256) |
| `title` | 187 on 236 | reverse + bold | Bound File, dirty `*`, HKT clock |
| `overdue` | 231 on 160 | white on red | Alarm stamp OVERDUE |
| `soon` | 232 on 178 | black on yellow | Alarm stamp SOON |
| `quiet` | 245 on 236 | dim | Empty alarm ribbon, hints, labels |
| `select` | 236 on 187 | reverse | Selected list row |
| `pin_note` / `pin_task` / `pin_event` / `pin_contact` | 75 / 208 / 141 / 73 | blue / yellow / magenta / cyan | One-letter pin only |
| `ok` / `err` / `rule` | 114 / 203 / 243 | green / red / dim | Status and ACS frames |

Monochrome: bold / reverse / dim. OVERDUE and SOON stay words.

### Layout

Master–detail diary. Type is a pin `N T E C`. Time is a right gutter.

```
┌ PIM  demo.pim* ────────────────────────────────────────── HKT 14:32 ┐
│ OVERDUE  Id 4  COMP3211 lecture  …              +2 more   d dismiss │
├ Current Result · type = event && … · 1 ─┬─ Detail · Id 4 · event ───┤
│   #  Id  · Name                  Time   │ COMP3211 lecture          │
│ > 1   4  E COMP3211 lecture  09-14 18:30│ start    2026-09-14 18:30 │
├─────────────────────────────────────────┴───────────────────────────┤
│ Created Event Id 4                                                  │
│ ↑↓ move   / search   c create   …   Esc clear                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Signature:** the Alarm Alert is a full-width diary stamp. Quiet ribbon when none due (`Alarms  ·  none`). `d` dismisses the first listed alarm. No alarm browser, no blinking clock.

---

## Checklist

| # | Item | Status |
|---|---|---|
| 1 | ADR-0018 + PRODUCT / ARCHITECTURE / ACCEPTANCE / AGENTS | **Done** |
| 2 | `view/theme.py` named roles, 256 / 8 / mono | **Done** |
| 3 | Diary paint: page, stamp, pins, paper selection, list headers, time gutter, `·` for missing time, criterion in list title, detail card | **Done** |
| 4 | `App.set_status(kind)`; View paints from kind; no substring sniffing | **Done** |
| 5 | Calendar: time slots below weekday header; selected day; today; summary; Tab focus | **Done** (unhandled keys in time focus still swallowed, as planned) |
| 6 | CJK caret + `input_window` so the caret stays in the field | **Done** |
| 7 | Chooser chips wrap; never drop an option | **Done** |
| 8 | Curses-only search retry; `criterion_line`; ghost example + grammar hint | **Done** (line UI / e2e do not re-prompt) |
| 9 | Idle `Esc` clears search; no-op if unfiltered; dirty prompt still ignores Esc | **Done** (`idle_escape` in Terminal; not a `keys.py` CHAR_ACTION) |
| 10 | Context footer: idle keys; `Esc clear` while filtered | **Done**. Wizard-open footer is still the chooser/picker hint, not a rewritten empty-Enter sentence in the title |
| 11 | Scroll cue `n–m of N` in the list pane title | **Done** |
| 12 | Dim diary under overlay; help grouped Move / Act / File; print overlay shows range | **Done** (help is grouped lines, not two visual columns) |
| 13 | Wizard titles `Create note · text` / `empty keeps` | **Partial** — search title is `Search — one criterion`; other fields still use the existing prompt labels (`text:`, `deadline [current] (empty keeps, none clears):`) |
| 14 | Empty / too-small / no-selection copy | **Done** (`No PIRs — press c, then pick a type`; too-small still shows the stamp if due; `q` quits) |
| 15 | Successful search selects the first hit | **Done** (syntax error still leaves Current Result) |
| 16 | Relative alarm amount selector (at start / 15 min / 1 hour / 1 day / Other…) | **Done**. Line UI still types the integer then unit |
| 17 | Idle `o` → `load` | **Dropped** — footer already dense; `: load` / `load` remain |

`keys.py` was **not** extended with CLEAR/LOAD accelerators. Esc-clear is a Terminal method the curses loop calls when idle.

---

## Architecture (as built)

Composition root unchanged: `PIM()` → `App(pim)` → `Terminal(app)` → `run()`.

```
view/
  theme.py        # colour roles, init_theme, attr()
  curses_ui.py    # TTY loop, paint, search retry, overlays
  layout.py       # Screen, pins, time gutter, list title, picker row helpers
  widgets.py      # Chooser, DateTimePicker, alarm_amount_chooser, wrap_chips
  textwidth.py    # caret_column, slice_columns, input_window
  keys.py         # empty-prompt accelerators (unchanged map)
  terminal.py     # wizards, _status, idle_escape, retry_search_prompt
controller/app.py # set_status, criterion_line, search() bool, first-hit select
```

No fifth package. `model` unchanged. `App.search` returns `False` on parse failure; the source line is stored only on success.

Snapshot/redraw from ADR-0010 stays: not every 500ms tick.

---

## Tests

| Layer | What landed |
|---|---|
| `tests/unit/test_theme.py` | Distinct pairs; mono reverse/dim; rich = 256 |
| `tests/unit/test_layout.py` | Pin + time gutter; `·` missing time; card_fields; criterion in title; picker time origin below weekdays |
| `tests/unit/test_textwidth.py` | CJK caret; input window keeps caret in width |
| `tests/unit/test_widgets.py` | Amount chooser payloads; wrap_chips never drops; relative alarm wizard uses the selector |
| `tests/unit/test_curses_ui.py` | Search syntax restores buffer; idle Esc clears / does not quit |
| `tests/unit/test_app.py` | `set_status` kind; search False; criterion_line; first-hit select |
| integration / e2e | Scripts unchanged except assertions that a successful search now selects the first hit (`print` after `search type = note`; list title shows the criterion) |

`python coverage_report.py` remains `model/` only. Unittest does not call `curses.initscr`.

---

## Manual check (macOS)

`python pim.py` plus ACCEPTANCE §6 typed as today. Also:

- Empty start: `c` is the next step.
- Alarm stamp is the only loud band; `d` dismisses; `.pim` unchanged.
- `/` shows an example; a typo keeps the line; `Esc` restores the whole collection.
- Calendar: weekday header and time list do not share cells; CJK caret sits on the glyph.
- Dirty `quit` cannot Esc-away.
- `PIM_NO_CURSES=1` and redirected stdin still match e2e.

---

## What this is not

Not a new product. Not a TUI framework. Not mouse, a theme picker, fuzzy search, or a visual query builder. Markers still type `search type = event && description contains "COMP"` in the demo video.
