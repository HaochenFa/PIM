# Interactive TTY uses stdlib curses; scripts keep the line UI

ADR-0004 locked “standard library only” and a designed terminal, and also said the submitted View would be clear-and-redraw, not `curses`. The assignment still forbids a GUI window and third-party TUI libraries. It does not forbid Python’s own `curses` module.

The TTY View is a full-screen stdlib `curses` session: titled panes, a visible selection, colour-coded Alarm Alerts, and keyboard accelerators around the same verb commands. Tests, redirected stdio, and `PIM_NO_CURSES=1` keep the line-oriented layout so stdin/stdout stay injectable.

This supersedes the “not curses” clause of ADR-0004. The rest of 0004 stands: no Textual/Rich/prompt_toolkit/Click, no pip, no GUI. It also specialises ADR-0010: on a TTY the 500ms tick is `get_wch` + `timeout(500)`; the stdin-reader thread remains the non-TTY loop. Only the main thread calls `model`. Redraw on change, not every tick. `curses` stays in `view`.

Keys (`/`, `c`, arrows, …) are accelerators for existing commands. They do not replace the criterion line or the field-by-field wizards (ADR-0013, ADR-0016). Colour is curses pairs, with an 8-colour and monochrome fallback.

**Status**: accepted
