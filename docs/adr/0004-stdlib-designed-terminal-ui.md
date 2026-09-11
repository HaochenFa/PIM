# Presentation uses the Python standard library only

The assignment grades implementation on using only the Java/Python standard library, and gives no extra credit for a GUI. Third-party TUI libraries (Textual, Rich, prompt_toolkit) are out.

The quality bar is still a designed terminal UI: visible structure, consistent navigation, confirmation on destructive actions, and readable errors. That is HCI for a CLI, not an extra product.

The submitted View is a redrawn stdlib layout (clear, regions, optional ANSI), not `curses` and not Textual. Swapping in `curses` later is a View-only change and is out of the plan unless explicitly reopened.

**Status**: accepted
