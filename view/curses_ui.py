"""Full-screen stdlib curses UI for an interactive TTY.

The session paints from ``view.layout.Screen``, feeds completed lines into
``Terminal._handle_line``, and restores the terminal through ``curses.wrapper``.
Only the main thread calls the model. The tick is ``timeout(500)`` so Alarm
Alerts appear without a keypress.
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

TYPE_PAIRS = {
    "note": PAIR_NOTE,
    "task": PAIR_TASK,
    "event": PAIR_EVENT,
    "contact": PAIR_CONTACT,
}

HELP_LINES = (
    "Keys  (empty prompt)",
    "  ↑ ↓  j k     select row of Current Result",
    "  PgUp PgDn    page the list",
    "  Home End     first / last row",
    "  /            search (criterion line)",
    "  c            create   m modify   p print   P print all",
    "  x Delete     delete (confirms y/n)    d dismiss alarm",
    "  w            save     q quit",
    "  :            type a full verb command",
    "  ?            this help",
    "",
    "Wizards and search still prompt field by field.",
    "Esc cancels a prompt. Ctrl-C / Ctrl-D are quit.",
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
            self.term.app.status = "Enter help for commands."
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

    def _snapshot(self):
        height, width = self.stdscr.getmaxyx()
        now = self.term._now_dt()
        clock = now.strftime("%Y-%m-%d %H:%M") if isinstance(now, datetime) else ""
        return (
            self.term._snapshot(),
            self.buffer,
            self.cursor,
            self.raw_command,
            self.show_help,
            self.print_open,
            self.print_scroll,
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

    def _fill(self, y: int, attr: int) -> None:
        height, width = self.stdscr.getmaxyx()
        if y < 0 or y >= height:
            return
        n = width if y < height - 1 else max(0, width - 1)
        try:
            self.stdscr.addstr(y, 0, " " * n, attr)
        except curses.error:
            pass

    def _draw(self) -> None:
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        geo = compute_geometry(height, width)
        self.term.page_size = max(1, geo.list_h)
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
        title_attr = self._attr(PAIR_TITLE, curses.A_BOLD)
        dirty_attr = self._attr(PAIR_SOON, curses.A_BOLD) if screen.dirty else title_attr
        self._put(geo.title_y, 0, screen.title, dirty_attr if screen.dirty else title_attr)
        if clock:
            clock_x = max(0, width - display_width(clock) - 1)
            self._put(geo.title_y, clock_x, clock, self._attr(PAIR_MUTED))
        self._draw_alarm(geo, screen, width)
        self._draw_list(geo, screen)
        self._draw_detail(geo, screen)
        if not geo.stacked:
            for y in range(geo.list_header_y, geo.status_y):
                try:
                    self.stdscr.addch(y, geo.list_w, curses.ACS_VLINE, self._attr(PAIR_RULE))
                except curses.error:
                    pass
        self._draw_status(geo, screen, width)
        self._put(geo.hints_y, 0, clip(HINTS, width - 1), self._attr(PAIR_MUTED))
        prompt = self._prompt_text(screen)
        self._put(geo.prompt_y, 0, clip(prompt, width - 1), self._attr(PAIR_TITLE))
        if self._is_dialog():
            self._draw_dialog(width, height)
        if self.print_open and screen.print_text:
            self._draw_overlay(width, height, "PRINT", screen.print_text, self.print_scroll)
        if self.show_help:
            self._draw_overlay(width, height, "HELP", "\n".join(HELP_LINES), 0)
        cursor_x = min(max(0, width - 2), self._cursor_col())
        try:
            curses.curs_set(0 if (self.show_help or self.print_open) else 1)
            self.stdscr.move(geo.prompt_y, cursor_x)
        except curses.error:
            pass
        self.stdscr.noutrefresh()
        curses.doupdate()

    def _draw_alarm(self, geo, screen, width: int) -> None:
        if not screen.alarms:
            self._fill(geo.alarm_y, self._attr(PAIR_MUTED))
            self._put(geo.alarm_y, 0, "  no alarms", self._attr(PAIR_MUTED))
            return
        first = screen.alarms[0]
        pair = PAIR_OVERDUE if first.status == "OVERDUE" else PAIR_SOON
        attr = self._attr(pair, curses.A_BOLD)
        extra = f"  +{len(screen.alarms) - 1} more" if len(screen.alarms) > 1 else ""
        text = (
            f"  {first.status}  Id {first.event_id}  {first.description}  "
            f"{first.when}{extra}    d dismiss"
        )
        self._fill(geo.alarm_y, attr)
        self._put(geo.alarm_y, 0, clip(text, width - 1), attr)

    def _draw_list(self, geo, screen) -> None:
        count = len(screen.rows)
        selected = next((i for i, row in enumerate(screen.rows) if row.selected), None)
        header = f" Current Result ({screen.filter_label})  {count} PIR(s)"
        self._put(geo.list_header_y, geo.list_x, clip(header, geo.list_w), self._attr(PAIR_TITLE, curses.A_BOLD))
        if geo.list_h <= 0:
            return
        if not screen.rows:
            self._put(
                geo.list_y,
                geo.list_x,
                clip("  No PIRs — press c to create", geo.list_w),
                self._attr(PAIR_MUTED, curses.A_BOLD),
            )
            return
        scroll = visible_list_window(count, selected, geo.list_h)
        for offset in range(geo.list_h):
            index = scroll + offset
            y = geo.list_y + offset
            if index >= count:
                break
            row = screen.rows[index]
            line = format_list_row(row, geo.list_w, short_time_col=True)
            if row.selected:
                attr = self._attr(PAIR_SELECT, curses.A_BOLD)
                self._put(y, geo.list_x, clip(line.ljust(geo.list_w), geo.list_w), attr)
            else:
                attr = self._attr(TYPE_PAIRS.get(row.type_name, PAIR_MUTED))
                self._put(y, geo.list_x, line, attr)

    def _draw_detail(self, geo, screen) -> None:
        if screen.selected_id is None:
            title = " DETAIL"
        else:
            kind = screen.detail[0][1] if screen.detail and screen.detail[0][0].casefold() == "type" else ""
            title = f" DETAIL  Id {screen.selected_id}" + (f"  {kind}" if kind else "")
        self._put(geo.detail_header_y, geo.detail_x, clip(title, geo.detail_w), self._attr(PAIR_TITLE, curses.A_BOLD))
        if geo.detail_h <= 0:
            return
        if not screen.detail:
            self._put(
                geo.detail_y,
                geo.detail_x,
                clip("  (no selection)", geo.detail_w),
                self._attr(PAIR_MUTED),
            )
            return
        y = geo.detail_y
        last = geo.detail_y + geo.detail_h
        label_w = min(14, geo.detail_w)
        for key, value in screen.detail:
            if y >= last:
                break
            self._put(y, geo.detail_x, clip(f"  {key}", label_w), self._attr(PAIR_MUTED))
            remain = geo.detail_w - label_w
            chunks = wrap(str(value), max(1, remain)) if remain > 0 else []
            if chunks:
                self._put(y, geo.detail_x + label_w, chunks[0], 0)
            y += 1
            for chunk in chunks[1:]:
                if y >= last:
                    break
                self._put(y, geo.detail_x + label_w, chunk, 0)
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
        self._put(geo.status_y, 0, clip(text, width - 1), attr)

    def _prompt_text(self, screen) -> str:
        if self.term._prompts:
            return screen.prompt + self.buffer
        if self.raw_command:
            return "> " + self.buffer
        if self.buffer:
            return "> " + self.buffer
        return screen.prompt if screen.prompt else "> "

    def _cursor_col(self) -> int:
        """Column of the caret: label width plus the buffer prefix before the caret."""
        if self.term._prompts:
            label = self.term._prompt_label()
        elif self.raw_command or self.buffer:
            label = "> "
        else:
            label = self.term._prompt_label() or "> "
        return display_width(label) + display_width(self.buffer[: self.cursor])

    def _is_dialog(self) -> bool:
        if self.term._is_dirty_prompt():
            return True
        label = self.term._prompt_label()
        return "[y/n]" in label or "save / discard / cancel" in label

    def _draw_dialog(self, width: int, height: int) -> None:
        question = self.term._prompt_label().rstrip()
        if question.endswith(":"):
            question = question[:-1].strip()
        lines = [clip(question, 48), "", "type an answer below, or Esc to cancel"]
        self._box(width, height, "Confirm", lines)

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
        attr = self._attr(PAIR_TITLE)
        for y in range(y0, y0 + box_h):
            self._put(y, x0, " " * min(box_w, width - x0 - (1 if y == height - 1 else 0)), attr)
        try:
            self.stdscr.hline(y0, x0, curses.ACS_HLINE, box_w)
            self.stdscr.hline(y0 + box_h - 1, x0, curses.ACS_HLINE, min(box_w, width - x0 - 1))
        except curses.error:
            pass
        self._put(y0, x0 + 1, clip(f" {title} ", box_w - 2), self._attr(PAIR_TITLE, curses.A_BOLD))
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
        if ch in (curses.KEY_ENTER, 10, 13, "\n", "\r"):
            self._submit()
            return
        if ch in (27, "\x1b"):
            self._escape()
            return
        if ch in (4, "\x04"):
            self._safe(self.term._handle_eof)
            return
        if ch in (3, "\x03"):
            self._safe(self.term._handle_interrupt)
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
