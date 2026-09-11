"""Named colour roles for the curses diary View.

Loud colour is only the Alarm Alert stamp. Everything else is ink on a
page: 256-colour night-study charcoal when the terminal allows it, an
8-colour fallback of reverse title/selection plus coloured type pins,
and bold/dim/reverse when there is no colour.
"""

from __future__ import annotations

PAGE = "page"
TITLE = "title"
OVERDUE = "overdue"
SOON = "soon"
SELECT = "select"
ERR = "err"
OK = "ok"
QUIET = "quiet"
RULE = "rule"
PIN_NOTE = "pin_note"
PIN_TASK = "pin_task"
PIN_EVENT = "pin_event"
PIN_CONTACT = "pin_contact"

PIN_ROLES = {
    "note": PIN_NOTE,
    "task": PIN_TASK,
    "event": PIN_EVENT,
    "contact": PIN_CONTACT,
}

TONE_ROLES = {
    "note": PIN_NOTE,
    "task": PIN_TASK,
    "event": PIN_EVENT,
    "contact": PIN_CONTACT,
    "ok": OK,
    "danger": ERR,
}

_PAIR = {
    PAGE: 1,
    TITLE: 2,
    OVERDUE: 3,
    SOON: 4,
    SELECT: 5,
    ERR: 6,
    OK: 7,
    QUIET: 8,
    PIN_NOTE: 9,
    PIN_TASK: 10,
    PIN_EVENT: 11,
    PIN_CONTACT: 12,
    RULE: 13,
}


class Theme:
    """Resolved curses attributes for one session."""

    def __init__(self, *, has_color: bool, colors: int = 0):
        self.has_color = has_color
        self.rich = bool(has_color and colors >= 256)
        self._curses = None

    def bind(self, curses_mod) -> None:
        """Attach the curses module after ``initscr``."""
        self._curses = curses_mod

    def attr(self, role: str, extra: int = 0) -> int:
        """Return a curses attribute integer for ``role``."""
        curses = self._curses
        if curses is None:
            return extra
        bits = extra
        if not self.has_color:
            if role in {SELECT, TITLE}:
                bits |= curses.A_REVERSE | curses.A_BOLD
            elif role in {OVERDUE, SOON, ERR}:
                bits |= curses.A_BOLD
            elif role in {QUIET, RULE}:
                bits |= curses.A_DIM
            return bits
        pair = _PAIR.get(role)
        if pair is not None:
            bits |= curses.color_pair(pair)
        if role in {TITLE, OVERDUE, SOON, SELECT, ERR}:
            bits |= curses.A_BOLD
        if role in {TITLE, SELECT} and not self.rich:
            bits |= curses.A_REVERSE
        return bits


def init_theme(curses_mod) -> Theme:
    """Start colour pairs and return a Theme bound to ``curses_mod``."""
    has = bool(curses_mod.has_colors())
    colors = int(getattr(curses_mod, "COLORS", 0) or 0) if has else 0
    theme = Theme(has_color=has, colors=colors)
    theme.bind(curses_mod)
    if not has:
        return theme
    curses_mod.start_color()
    background = -1
    try:
        curses_mod.use_default_colors()
    except curses_mod.error:
        background = curses_mod.COLOR_BLACK
    if theme.rich:
        _init_rich(curses_mod)
    else:
        _init_eight(curses_mod, background)
    return theme


def _init_rich(curses_mod) -> None:
    """256-colour night-study page. Stamp is the only filled band."""
    init = curses_mod.init_pair
    init(_PAIR[PAGE], 253, 236)
    init(_PAIR[TITLE], 187, 236)
    init(_PAIR[OVERDUE], 231, 160)
    init(_PAIR[SOON], 232, 178)
    init(_PAIR[SELECT], 236, 187)
    init(_PAIR[ERR], 203, 236)
    init(_PAIR[OK], 114, 236)
    init(_PAIR[QUIET], 245, 236)
    init(_PAIR[PIN_NOTE], 75, 236)
    init(_PAIR[PIN_TASK], 208, 236)
    init(_PAIR[PIN_EVENT], 141, 236)
    init(_PAIR[PIN_CONTACT], 73, 236)
    init(_PAIR[RULE], 243, 236)


def _init_eight(curses_mod, background: int) -> None:
    """8-colour fallback: reverse title/selection, coloured pins, red/amber stamp."""
    init = curses_mod.init_pair
    fg_white = curses_mod.COLOR_WHITE
    init(_PAIR[PAGE], fg_white, background)
    init(_PAIR[TITLE], fg_white, background)
    init(_PAIR[OVERDUE], curses_mod.COLOR_WHITE, curses_mod.COLOR_RED)
    init(_PAIR[SOON], curses_mod.COLOR_BLACK, curses_mod.COLOR_YELLOW)
    init(_PAIR[SELECT], curses_mod.COLOR_BLACK, curses_mod.COLOR_WHITE)
    init(_PAIR[ERR], curses_mod.COLOR_RED, background)
    init(_PAIR[OK], curses_mod.COLOR_GREEN, background)
    init(_PAIR[QUIET], fg_white, background)
    init(_PAIR[PIN_NOTE], curses_mod.COLOR_BLUE, background)
    init(_PAIR[PIN_TASK], curses_mod.COLOR_YELLOW, background)
    init(_PAIR[PIN_EVENT], curses_mod.COLOR_MAGENTA, background)
    init(_PAIR[PIN_CONTACT], curses_mod.COLOR_CYAN, background)
    init(_PAIR[RULE], fg_white, background)
