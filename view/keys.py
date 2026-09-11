"""Empty-prompt key accelerators for the designed terminal.

Full verb commands still work. Letters in ``CHAR_ACTIONS`` run immediately
only when the prompt buffer is empty and no wizard is open, so they do not
steal characters already typed. ``:`` (handled in the curses UI) starts a
raw command line for the same verbs used by the non-TTY fallback.
"""

from __future__ import annotations

SELECT_UP = "select_up"
SELECT_DOWN = "select_down"
SELECT_PAGE_UP = "select_page_up"
SELECT_PAGE_DOWN = "select_page_down"
SELECT_FIRST = "select_first"
SELECT_LAST = "select_last"
SEARCH = "search"
CREATE = "create"
MODIFY = "modify"
PRINT = "print"
PRINT_ALL = "print_all"
DELETE = "delete"
DISMISS = "dismiss"
SAVE = "save"
HELP = "help"
QUIT = "quit"
COMMAND = "command"

CHAR_ACTIONS = {
    "/": SEARCH,
    "c": CREATE,
    "m": MODIFY,
    "p": PRINT,
    "P": PRINT_ALL,
    "x": DELETE,
    "d": DISMISS,
    "w": SAVE,
    "?": HELP,
    "q": QUIT,
    "j": SELECT_DOWN,
    "k": SELECT_UP,
    ":": COMMAND,
}

KEY_ACTIONS = {
    "KEY_UP": SELECT_UP,
    "KEY_DOWN": SELECT_DOWN,
    "KEY_PPAGE": SELECT_PAGE_UP,
    "KEY_NPAGE": SELECT_PAGE_DOWN,
    "KEY_HOME": SELECT_FIRST,
    "KEY_END": SELECT_LAST,
    "KEY_DC": DELETE,
}

PRINT_ACTIONS = {PRINT, PRINT_ALL}


def action_for_char(char: str) -> str | None:
    """Return the accelerator for a one-character key, or None."""
    if len(char) != 1:
        return None
    return CHAR_ACTIONS.get(char)


def action_for_key_name(name: str) -> str | None:
    """Return the accelerator for a curses key name such as ``KEY_UP``."""
    return KEY_ACTIONS.get(name)
