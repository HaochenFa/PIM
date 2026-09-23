# Presentation uses the Python standard library only

The assignment grades implementation on using only the Java/Python standard library, and gives no extra credit for a GUI. Third-party TUI libraries (Textual, Rich, prompt_toolkit) are out.

The quality bar is still a designed terminal UI: visible structure, consistent navigation, confirmation on destructive actions, and readable errors. That is HCI for a CLI, not an extra product.

The submitted View is a designed terminal, not a GUI and not Textual. The “not curses” clause is **superseded by ADR-0018**: an interactive TTY uses stdlib `curses`; scripts and tests keep a line-oriented layout.

**Status**: accepted (curses clause superseded by ADR-0018)
