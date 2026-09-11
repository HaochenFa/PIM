"""Full-screen stdlib curses UI for an interactive TTY.

Panes are titled widgets (title, alarms, Current Result, detail, composer).
Closed answers use a ``Chooser`` (type, yes/no, alarm kind/unit, dirty
save). Free text still goes through ``Terminal._handle_line``. The tick is
``timeout(500)`` so Alarm Alerts appear without a keypress.
"""

from __future__ import annotations

import curses
from datetime import datetime

from controller.errors import message_for
from model import PIMError
from model.pir import HKT
from view.keys import COMMAND, HELP as KEY_HELP, action_for_char, action_for_key_name
from view.layout import HINTS, MENU, compute_geometry, format_list_row, visible_list_window
from view.textwidth import clip, display_width, wrap
from view.widgets import Chooser, composer_height

PAIR_TITLE = 1
PAIR_OVERDUE = 2
PAIR_SOON = 3
PAIR_SELECT = 4
PAIR_ERR = 5
PAIR_OK = 6
PAIR_MUTED = 7
PAIR_NOTE = 8
PAIR_TASK = 9
PAIR_EVENT = 10
PAIR_CONTACT = 11
PAIR_RULE = 12
PAIR_BAR = 13

TYPE_PAIRS = {
    "note": PAIR_NOTE,
    "task": PAIR_TASK,
    "event": PAIR_EVENT,
    "contact": PAIR_CONTACT,
}

TONE_PAIRS = {
    "note": PAIR_NOTE,
    "task": PAIR_TASK,
    "event": PAIR_EVENT,
    "contact": PAIR_CONTACT,
    "ok": PAIR_OK,
    "danger": PAIR_ERR,
}

HELP_LINES = (
    "Keys  (nothing being asked)",
    "  ↑ ↓  j k     move in Current Result",
    "  /            search",
    "  c            create — then pick a type with ← → or n/t/e/c",
    "  m            modify   p print   P print all",
    "  x Delete     delete — Yes/No selector",
    "  d            dismiss alarm    w save    q quit",
    "  :            type a full verb command",
    "  ?            this help",
    "",
    "When a selector is open: arrows move, Enter confirms, a letter or",
    "number picks, Esc cancels. You never have to type 'note' or 'yes'.",
    "",
    MENU,
    "",
    "Any key closes this help.",
)


def run_curses(terminal) -> None:
    """Run the curses session for ``terminal`` until it stops."""
    curses.wrapper(lambda stdscr: CursesUI(terminal, stdscr).loop())


def init_pairs() -> None:
    """Define 8-colour pairs. No-op when the terminal has no colour."""
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
        background = -1
    except curses.error:
        background = curses.COLOR_BLACK
    curses.init_pair(PAIR_TITLE, curses.COLOR_CYAN, background)
    curses.init_pair(PAIR_OVERDUE, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(PAIR_SOON, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(PAIR_SELECT, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(PAIR_ERR, curses.COLOR_RED, background)
    curses.init_pair(PAIR_OK, curses.COLOR_GREEN, background)
    curses.init_pair(PAIR_MUTED, curses.COLOR_WHITE, background)
    curses.init_pair(PAIR_NOTE, curses.COLOR_BLUE, background)
    curses.init_pair(PAIR_TASK, curses.COLOR_GREEN, background)
    curses.init_pair(PAIR_EVENT, curses.COLOR_MAGENTA, background)
    curses.init_pair(PAIR_CONTACT, curses.COLOR_CYAN, background)
    curses.init_pair(PAIR_RULE, curses.COLOR_WHITE, background)
    curses.init_pair(PAIR_BAR, curses.COLOR_BLACK, curses.COLOR_CYAN)


class CursesUI:
    """One curses session bound to a ``Terminal``."""

    def __init__(self, terminal, stdscr):
        self.term = terminal
        self.stdscr = stdscr
        self.buffer = ""
        self.cursor = 0
        self.raw_command = False
        self.show_help = False
        self.print_open = False
        self.print_scroll = 0
        self.choice_index = 0
        self._chooser_id = None
        self._last_snapshot = None
        self._has_color = False

    def loop(self) -> None:
        """Main loop: paint on change, ``get_wch`` with a 500ms timeout."""
        curses.curs_set(1)
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.stdscr.timeout(500)
        init_pairs()
        self._has_color = bool(curses.has_colors())
        self.term._running = True
        if not self.term.app.status:
            self.term.app.status = "c create   / search   ? help"
        self._paint(force=True)
        while self.term._running:
            self._paint(force=False)
            try:
                ch = self.stdscr.get_wch()
            except curses.error:
                continue
            except KeyboardInterrupt:
                self._safe(self.term._handle_interrupt)
                continue
            self._handle_key(ch)

    def _attr(self, pair: int, extra: int = 0) -> int:
        if not self._has_color:
            return extra
        return curses.color_pair(pair) | extra

    def _sync_chooser(self) -> Chooser | None:
        """Reset the highlight when a new selector appears."""
        chooser = self.term.current_chooser()
        ident = id(chooser) if chooser is not None else None
        if ident != self._chooser_id:
            self._chooser_id = ident
            self.choice_index = chooser.default if chooser is not None else 0
        if chooser is not None:
            self.choice_index = chooser.clamp(self.choice_index)
        return chooser

    def _composer_h(self) -> int:
        chooser = self.term.current_chooser()
        text_prompt = bool(self.term._prompts) or self.raw_command or bool(self.buffer)
        return composer_height(chooser=chooser, text_prompt=text_prompt)

    def _snapshot(self):
        height, width = self.stdscr.getmaxyx()
        now = self.term._now_dt()
        clock = now.strftime("%Y-%m-%d %H:%M") if isinstance(now, datetime) else ""
        chooser = self.term.current_chooser()
        return (
            self.term._snapshot(),
            self.buffer,
            self.cursor,
            self.raw_command,
            self.show_help,
            self.print_open,
            self.print_scroll,
            self.choice_index,
            None if chooser is None else chooser.title,
            height,
            width,
            clock,
        )

    def _paint(self, force: bool) -> None:
        snap = self._snapshot()
        if not force and snap == self._last_snapshot:
            return
        self._draw()
        self._last_snapshot = snap

    def _put(self, y: int, x: int, text: str, attr: int = 0, width: int | None = None) -> None:
        height, width_scr = self.stdscr.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width_scr:
            return
        limit = width_scr - x
        if y == height - 1:
            limit = max(0, limit - 1)
        if width is not None:
            limit = min(limit, width)
        if limit <= 0:
            return
        piece = clip(str(text).replace("\t", " "), limit)
        try:
            self.stdscr.addstr(y, x, piece, attr)
        except curses.error:
            pass

    def _fill(self, y: int, attr: int, x: int = 0, width: int | None = None) -> None:
        height, scr_w = self.stdscr.getmaxyx()
        if y < 0 or y >= height:
            return
        span = scr_w - x if width is None else width
        if y == height - 1:
            span = min(span, max(0, scr_w - x - 1))
        if span <= 0:
            return
        try:
            self.stdscr.addstr(y, x, " " * span, attr)
        except curses.error:
            pass

    def _frame(self, y: int, x: int, h: int, w: int, title: str, attr: int = 0) -> None:
        """Titled widget border using ACS line drawing."""
        if h < 2 or w < 2:
            self._put(y, x, clip(title, max(0, w)), attr | curses.A_BOLD)
            return
        try:
            self.stdscr.hline(y, x, curses.ACS_HLINE, w)
            bottom = y + h - 1
            self.stdscr.hline(bottom, x, curses.ACS_HLINE, w)
            for row in range(y + 1, bottom):
                self.stdscr.addch(row, x, curses.ACS_VLINE, attr)
                if x + w - 1 >= 0:
                    self.stdscr.addch(row, x + w - 1, curses.ACS_VLINE, attr)
            self.stdscr.addch(y, x, curses.ACS_ULCORNER, attr)
            self.stdscr.addch(y, x + w - 1, curses.ACS_URCORNER, attr)
            self.stdscr.addch(bottom, x, curses.ACS_LLCORNER, attr)
            self.stdscr.addch(bottom, x + w - 1, curses.ACS_LRCORNER, attr)
        except curses.error:
            pass
        if title:
            label = clip(f" {title} ", max(0, w - 2))
            self._put(y, x + 1, label, attr | curses.A_BOLD)

    def _draw(self) -> None:
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        chooser = self._sync_chooser()
        geo = compute_geometry(height, width, self._composer_h())
        self.term.page_size = max(1, geo.list_h - 1)
        if geo.too_small:
            self._put(0, 0, "Widen the terminal to use the PIM.", self._attr(PAIR_ERR, curses.A_BOLD))
            self._put(1, 0, "q quits.", self._attr(PAIR_MUTED))
            self.stdscr.move(min(2, height - 1), 0)
            self.stdscr.noutrefresh()
            curses.doupdate()
            return
        screen = self.term.screen()
        now = self.term._now_dt()
        clock = now.astimezone(HKT).strftime("HKT %H:%M") if isinstance(now, datetime) else ""
        bar = self._attr(PAIR_BAR, curses.A_BOLD)
        self._fill(geo.title_y, bar)
        self._put(geo.title_y, 1, screen.title, bar)
        if clock:
            clock_x = max(0, width - display_width(clock) - 2)
            self._put(geo.title_y, clock_x, clock, bar)
        self._draw_alarm(geo, screen, width)
        self._draw_panes(geo, screen)
        self._draw_status(geo, screen, width)
        self._draw_composer(geo, screen, chooser, width)
        if self.print_open and screen.print_text:
            self._draw_overlay(width, height, "PRINT", screen.print_text, self.print_scroll)
        if self.show_help:
            self._draw_overlay(width, height, "HELP", "\n".join(HELP_LINES), 0)
        hide_cursor = bool(chooser) or self.show_help or self.print_open
        if not hide_cursor and not (self.term._prompts or self.raw_command or self.buffer):
            hide_cursor = True
        try:
            curses.curs_set(0 if hide_cursor else 1)
            if not hide_cursor:
                cursor_x = min(max(0, width - 2), 2 + display_width(self.buffer[: self.cursor]))
                self.stdscr.move(geo.composer_y + 1, cursor_x)
        except curses.error:
            pass
        self.stdscr.noutrefresh()
        curses.doupdate()

    def _draw_alarm(self, geo, screen, width: int) -> None:
        if not screen.alarms:
            self._fill(geo.alarm_y, self._attr(PAIR_MUTED))
            self._put(geo.alarm_y, 1, "Alarms  none due", self._attr(PAIR_MUTED))
            return
        first = screen.alarms[0]
        pair = PAIR_OVERDUE if first.status == "OVERDUE" else PAIR_SOON
        attr = self._attr(pair, curses.A_BOLD)
        extra = f"  +{len(screen.alarms) - 1} more" if len(screen.alarms) > 1 else ""
        text = (
            f" {first.status}  Id {first.event_id}  {first.description}  "
            f"{first.when}{extra}   d dismiss"
        )
        self._fill(geo.alarm_y, attr)
        self._put(geo.alarm_y, 0, clip(text, width - 1), attr)

    def _draw_panes(self, geo, screen) -> None:
        count = len(screen.rows)
        list_title = f"Current Result · {screen.filter_label} · {count}"
        if screen.selected_id is None:
            detail_title = "Detail"
        else:
            kind = ""
            for key, value in screen.detail:
                if key.casefold() == "type":
                    kind = str(value)
                    break
            detail_title = f"Detail · Id {screen.selected_id}" + (f" · {kind}" if kind else "")
        rule = self._attr(PAIR_RULE)
        if geo.stacked:
            list_h = geo.detail_header_y - geo.list_header_y
            detail_h = geo.status_y - geo.detail_header_y
            self._frame(geo.list_header_y, 0, list_h, geo.width, list_title, rule)
            self._frame(geo.detail_header_y, 0, detail_h, geo.width, detail_title, rule)
        else:
            pane_h = geo.status_y - geo.list_header_y
            self._frame(geo.list_header_y, 0, pane_h, geo.list_w, list_title, rule)
            self._frame(geo.detail_header_y, geo.detail_x, pane_h, geo.detail_w, detail_title, rule)
        self._draw_list(geo, screen)
        self._draw_detail(geo, screen)

    def _draw_list(self, geo, screen) -> None:
        inner_x = geo.list_x + 1
        inner_w = max(1, geo.list_w - 2)
        y = geo.list_y
        last = min(geo.list_y + geo.list_h, geo.status_y - 1)
        if y >= last:
            return
        if not screen.rows:
            self._put(
                y,
                inner_x,
                clip("No PIRs — press c, then pick a type", inner_w),
                self._attr(PAIR_MUTED, curses.A_BOLD),
            )
            return
        selected = next((i for i, row in enumerate(screen.rows) if row.selected), None)
        height = last - y
        scroll = visible_list_window(len(screen.rows), selected, height)
        for offset in range(height):
            index = scroll + offset
            if index >= len(screen.rows):
                break
            row = screen.rows[index]
            line = format_list_row(row, inner_w, short_time_col=True)
            if row.selected:
                attr = self._attr(PAIR_SELECT, curses.A_BOLD)
                self._fill(y + offset, attr, inner_x, inner_w)
                self._put(y + offset, inner_x, clip(line, inner_w), attr)
            else:
                attr = self._attr(TYPE_PAIRS.get(row.type_name, PAIR_MUTED))
                self._put(y + offset, inner_x, line, attr)

    def _draw_detail(self, geo, screen) -> None:
        inner_x = geo.detail_x + 1
        inner_w = max(1, geo.detail_w - 2)
        y = geo.detail_y
        last = min(geo.detail_y + geo.detail_h, geo.status_y - 1)
        if y >= last:
            return
        if not screen.detail:
            self._put(y, inner_x, clip("Select a row to read it here", inner_w), self._attr(PAIR_MUTED))
            return
        label_w = min(14, inner_w)
        for key, value in screen.detail:
            if y >= last:
                break
            self._put(y, inner_x, clip(key, label_w), self._attr(PAIR_MUTED))
            remain = inner_w - label_w
            chunks = wrap(str(value), max(1, remain)) if remain > 0 else []
            if chunks:
                self._put(y, inner_x + label_w, chunks[0], 0)
            y += 1
            for chunk in chunks[1:]:
                if y >= last:
                    break
                self._put(y, inner_x + label_w, chunk, 0)
                y += 1

    def _draw_status(self, geo, screen, width: int) -> None:
        text = screen.status
        lower = text.casefold()
        err_marks = (
            "unknown",
            "required",
            "fail",
            "error",
            "invalid",
            "cannot",
            "no pir",
            "no row",
            "no alarm",
            "cancelled",
            "syntax",
            "not a",
            "must ",
        )
        if any(mark in lower for mark in err_marks):
            attr = self._attr(PAIR_ERR, curses.A_BOLD)
        elif text:
            attr = self._attr(PAIR_OK)
        else:
            attr = self._attr(PAIR_MUTED)
        self._fill(geo.status_y, self._attr(PAIR_MUTED))
        self._put(geo.status_y, 1, clip(text, width - 2), attr)

    def _draw_composer(self, geo, screen, chooser: Chooser | None, width: int) -> None:
        rule = self._attr(PAIR_TITLE)
        if chooser is not None:
            self._frame(geo.composer_y, 0, geo.composer_h, width, chooser.title, rule)
            self._draw_chips(geo.composer_y + 1, 2, max(1, width - 4), chooser, self.choice_index)
            if geo.composer_h >= 3:
                self._put(
                    geo.composer_y + geo.composer_h - 1,
                    2,
                    clip(chooser.hint, width - 4),
                    self._attr(PAIR_MUTED),
                )
            return
        if self.term._prompts or self.raw_command or self.buffer:
            label = self._field_title(screen)
            self._frame(geo.composer_y, 0, geo.composer_h, width, label, rule)
            field = self.buffer
            self._put(geo.composer_y + 1, 2, clip(field if field else " ", width - 4), 0)
            return
        self._fill(geo.composer_y, self._attr(PAIR_MUTED))
        self._put(geo.composer_y, 1, clip(HINTS, width - 2), self._attr(PAIR_MUTED))
        if geo.composer_h > 1:
            self._fill(geo.composer_y + 1, self._attr(PAIR_MUTED))
            self._put(
                geo.composer_y + 1,
                1,
                clip("▸  type a command after :    or press a key above", width - 2),
                self._attr(PAIR_MUTED),
            )

    def _field_title(self, screen) -> str:
        if self.raw_command:
            return "Command"
        label = screen.prompt.rstrip()
        if label.endswith(":"):
            label = label[:-1].strip()
        return label or "Input"

    def _draw_chips(self, y: int, x: int, width: int, chooser: Chooser, index: int) -> None:
        """Horizontal option chips. Falls back to a single highlighted label if tight."""
        cursor = x
        limit = x + width
        for i, option in enumerate(chooser.options):
            selected = i == index
            key = option.key or str(i + 1)
            body = f" {key} {option.label} "
            w = display_width(body)
            if cursor + w > limit:
                if i == 0:
                    self._put(y, x, clip(body, width), self._chip_attr(option.tone, selected))
                break
            self._put(y, cursor, body, self._chip_attr(option.tone, selected))
            cursor += w + 1

    def _chip_attr(self, tone: str | None, selected: bool) -> int:
        pair = TONE_PAIRS.get(tone or "", PAIR_TITLE)
        extra = curses.A_REVERSE | curses.A_BOLD if selected else curses.A_BOLD
        return self._attr(pair, extra)

    def _draw_overlay(self, width: int, height: int, title: str, body: str, scroll: int) -> None:
        inner_w = min(width - 4, max(40, width * 3 // 4))
        inner_h = min(height - 4, max(8, height * 3 // 4))
        wrapped: list[str] = []
        for raw in body.splitlines() or [""]:
            wrapped.extend(wrap(raw if raw else " ", inner_w - 4) or [" "])
        max_scroll = max(0, len(wrapped) - (inner_h - 2))
        scroll = min(max(0, scroll), max_scroll)
        view = wrapped[scroll : scroll + inner_h - 2]
        self._box(width, height, title, view, box_w=inner_w, box_h=inner_h)

    def _box(self, width: int, height: int, title: str, lines: list[str], box_w=None, box_h=None) -> None:
        box_w = box_w or min(width - 4, max(36, max((display_width(line) for line in lines), default=20) + 4))
        box_h = box_h or min(height - 2, len(lines) + 2)
        box_w = max(20, min(box_w, width - 2))
        box_h = max(3, min(box_h, height - 2))
        y0 = max(0, (height - box_h) // 2)
        x0 = max(0, (width - box_w) // 2)
        self._frame(y0, x0, box_h, box_w, title, self._attr(PAIR_TITLE))
        for i, line in enumerate(lines[: box_h - 2]):
            self._put(y0 + 1 + i, x0 + 2, clip(line, box_w - 4), 0)

    def _safe(self, fn) -> None:
        try:
            fn()
        except PIMError as exc:
            self.term.app.status = message_for(exc)
        except OSError as exc:
            self.term.app.status = message_for(exc)

    def _handle_key(self, ch) -> None:
        if ch == curses.KEY_RESIZE:
            self._paint(force=True)
            return
        if self.show_help:
            self.show_help = False
            return
        if self.print_open:
            if self._handle_print_key(ch):
                return
        if ch in (4, "\x04"):
            self._safe(self.term._handle_eof)
            return
        if ch in (3, "\x03"):
            self._safe(self.term._handle_interrupt)
            return
        self._sync_chooser()
        if self.term.current_chooser() is not None:
            if self._handle_chooser_key(ch):
                return
        if ch in (curses.KEY_ENTER, 10, 13, "\n", "\r"):
            self._submit()
            return
        if ch in (27, "\x1b"):
            self._escape()
            return
        editing = bool(self.term._prompts) or self.raw_command or bool(self.buffer)
        if not editing:
            action = self._action(ch)
            if action == COMMAND:
                self.raw_command = True
                self.buffer = ""
                self.cursor = 0
                return
            if action == KEY_HELP:
                self.show_help = True
                return
            if action is not None:
                before = self.term.app.print_text
                self._safe(lambda: self.term.apply_accelerator(action))
                if self.term.app.print_text and self.term.app.print_text != before:
                    self.print_open = True
                    self.print_scroll = 0
                return
        self._edit(ch)

    def _handle_chooser_key(self, ch) -> bool:
        """True when the selector consumed the key."""
        chooser = self.term.current_chooser()
        if chooser is None:
            return False
        if ch in (curses.KEY_ENTER, 10, 13, "\n", "\r"):
            self._chooser_submit(chooser)
            return True
        if ch in (27, "\x1b"):
            self._escape()
            return True
        if ch in (curses.KEY_LEFT, curses.KEY_UP, "h", "k"):
            self.choice_index = chooser.move(self.choice_index, -1)
            return True
        if ch in (curses.KEY_RIGHT, curses.KEY_DOWN, "l", "j"):
            self.choice_index = chooser.move(self.choice_index, 1)
            return True
        if ch in (curses.KEY_HOME,):
            self.choice_index = 0
            return True
        if ch in (curses.KEY_END,):
            self.choice_index = chooser.clamp(len(chooser.options) - 1)
            return True
        if isinstance(ch, str) and len(ch) == 1:
            picked = chooser.pick_key(ch)
            if picked is not None:
                self.choice_index = picked
                self._chooser_submit(chooser)
                return True
        return True

    def _chooser_submit(self, chooser: Chooser) -> None:
        value = chooser.value_at(self.choice_index)
        self.buffer = ""
        self.cursor = 0
        before = self.term.app.print_text
        self._safe(lambda: self.term._handle_line(value))
        if self.term.app.print_text and self.term.app.print_text != before:
            self.print_open = True
            self.print_scroll = 0

    def _action(self, ch) -> str | None:
        if isinstance(ch, str):
            return action_for_char(ch)
        name = curses.keyname(ch)
        if isinstance(name, bytes):
            name = name.decode("ascii", "replace")
        return action_for_key_name(name)

    def _handle_print_key(self, ch) -> bool:
        if ch in (27, "\x1b", "q", "Q", curses.KEY_ENTER, 10, 13, "\n", "\r"):
            self.print_open = False
            return True
        if ch in (curses.KEY_UP, "k"):
            self.print_scroll = max(0, self.print_scroll - 1)
            return True
        if ch in (curses.KEY_DOWN, "j"):
            self.print_scroll += 1
            return True
        if ch == curses.KEY_PPAGE:
            self.print_scroll = max(0, self.print_scroll - 10)
            return True
        if ch == curses.KEY_NPAGE:
            self.print_scroll += 10
            return True
        return False

    def _submit(self) -> None:
        line = self.buffer
        self.buffer = ""
        self.cursor = 0
        self.raw_command = False
        before = self.term.app.print_text
        self._safe(lambda: self.term._handle_line(line))
        if self.term.app.print_text and self.term.app.print_text != before:
            self.print_open = True
            self.print_scroll = 0

    def _escape(self) -> None:
        if self.print_open:
            self.print_open = False
            return
        if self.buffer or self.raw_command:
            self.buffer = ""
            self.cursor = 0
            self.raw_command = False
            self.term.app.status = "command cancelled"
            return
        self._safe(self.term.cancel_prompt)

    def _edit(self, ch) -> None:
        if ch in (curses.KEY_BACKSPACE, 127, 8, "\x7f", "\b"):
            if self.cursor > 0:
                self.buffer = self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
                self.cursor -= 1
            return
        if ch == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
            return
        if ch == curses.KEY_RIGHT:
            self.cursor = min(len(self.buffer), self.cursor + 1)
            return
        if ch in (curses.KEY_HOME,):
            self.cursor = 0
            return
        if ch in (curses.KEY_END,):
            self.cursor = len(self.buffer)
            return
        if ch == curses.KEY_DC:
            self.buffer = self.buffer[: self.cursor] + self.buffer[self.cursor + 1 :]
            return
        if isinstance(ch, str) and ch.isprintable():
            self.buffer = self.buffer[: self.cursor] + ch + self.buffer[self.cursor :]
            self.cursor += 1
