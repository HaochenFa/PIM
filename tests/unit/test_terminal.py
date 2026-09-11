"""view.Terminal: command dispatch, wizards, layout, dismiss. App is faked."""

from __future__ import annotations

import io
import unittest
from datetime import datetime

from model import Event, Note, RelativeAlarm
from model.pir import HKT, parse_datetime
from view.terminal import MENU, Terminal


class FakeDue:
    """One due alarm for the banner."""

    def __init__(self, event_id=4, alarm_index=0, status="OVERDUE"):
        self.event_id = event_id
        self.alarm_index = alarm_index
        self.status = status
        self.at = parse_datetime("2026-09-14T18:30:00+08:00")
        self.description = "lecture"

    def key(self):
        """Dismiss identity."""
        return (self.event_id, self.alarm_index)


class FakeApp:
    """App stand-in: records calls, holds list/selection/status."""

    def __init__(self):
        self.status = ""
        self.print_text = ""
        self._dirty = False
        self._bound = None
        self._result = []
        self._selected = None
        self._criterion = False
        self._due = []
        self.calls = []
        self.save_ok = True
        self.load_ok = True
        self.overwrite = False
        self.created = None
        self.modified = None
        self.save_raises = None

    def bound_path(self):
        return self._bound

    def is_dirty(self) -> bool:
        return self._dirty

    def save_target(self, path) -> str:
        text = str(path)
        return text if text.endswith(".pim") else text + ".pim"

    def would_overwrite(self, path) -> bool:
        return self.overwrite

    def clear_print(self):
        self.print_text = ""

    def current_result(self):
        return list(self._result)

    def selected(self):
        return self._selected

    def selected_id(self):
        return None if self._selected is None else self._selected.id

    def has_criterion(self) -> bool:
        return self._criterion

    def due_alarms(self, now):
        return list(self._due)

    def create(self, type_name, fields):
        self.calls.append(("create", type_name, fields))
        self.status = f"Created {type_name} Id 1"
        return self.created

    def modify(self, fields):
        self.calls.append(("modify", fields))
        self.status = "Modified"
        if self.modified is not None:
            return self.modified
        return self._selected

    def delete_selected(self):
        self.calls.append(("delete",))
        self.status = "Deleted"
        self._selected = None
        return True

    def search(self, line: str):
        self.calls.append(("search", line))
        self._criterion = True
        self.status = "1 match(es)"

    def clear_search(self):
        self.calls.append(("clear",))
        self._criterion = False
        self.status = "Search cleared"

    def select_row(self, number):
        self.calls.append(("row", number))
        try:
            index = int(number)
        except (TypeError, ValueError):
            return
        if 1 <= index <= len(self._result):
            self._selected = self._result[index - 1]

    def select_id(self, pir_id):
        self.calls.append(("id", pir_id))

    def print_selected(self):
        self.print_text = "one"
        self.status = "Printed Id 1"
        return self.print_text

    def print_all(self):
        self.print_text = "all"
        self.status = "Printed 0 PIR(s) in Current Result"
        return self.print_text

    def save(self, path=None):
        if self.save_raises:
            raise self.save_raises
        self.calls.append(("save", path))
        if not self.save_ok:
            self.status = "save failed"
            return False
        self._dirty = False
        if path:
            self._bound = str(path)
        self.status = f"Saved {self._bound}"
        return True

    def load(self, path, force=False):
        self.calls.append(("load", path, force))
        if not self.load_ok:
            self.status = "load failed"
            return False
        self._dirty = False
        self._bound = str(path)
        self.status = f"Loaded {path}"
        return True


def make_terminal(app=None, now=None, tty=False):
    """Terminal bound to `app` (or a new FakeApp) writing to StringIO."""
    if app is None:
        app = FakeApp()
    stdout = TtyBuffer() if tty else io.StringIO()
    term = Terminal(app, stdin=io.StringIO(), stdout=stdout, now=now)
    return app, term, stdout


class TtyBuffer(io.StringIO):
    """StringIO that reports as a TTY so render uses ANSI clear."""

    def isatty(self) -> bool:
        return True


def feed(term: Terminal, *lines: str) -> None:
    """Push completed lines through the View without the event loop."""
    for line in lines:
        term._handle_line(line)


class CommandDispatchTests(unittest.TestCase):
    def test_blank_line_is_ignored(self):
        app, term, _out = make_terminal()
        feed(term, "", "   ")
        self.assertEqual(app.calls, [])
        self.assertEqual(app.status, "")

    def test_help_clear_print_and_aliases(self):
        app, term, _out = make_terminal()
        feed(term, "help")
        self.assertIn("create", app.status)
        feed(term, "clear")
        self.assertEqual(app.calls[-1], ("clear",))
        feed(term, "print")
        self.assertEqual(app.print_text, "one")
        feed(term, "print all")
        self.assertEqual(app.print_text, "all")
        feed(term, "1")
        self.assertEqual(app.calls[-1], ("row", "1"))
        feed(term, "id 4")
        self.assertEqual(app.calls[-1], ("id", "4"))
        app._dirty = False
        term._running = True
        feed(term, "q")
        self.assertFalse(term._running)
        self.assertNotEqual(app.status, "unknown command: q")
        _, term2, _ = make_terminal()
        term2._running = True
        feed(term2, "exit")
        self.assertFalse(term2._running)

    def test_unknown_command_and_non_print_clears_print_text(self):
        app, term, _out = make_terminal()
        app.print_text = "keep"
        feed(term, "print")
        self.assertEqual(app.print_text, "one")
        feed(term, "help")
        self.assertEqual(app.print_text, "")
        feed(term, "explode")
        self.assertEqual(app.status, "unknown command: explode")

    def test_search_inline_or_prompted(self):
        app, term, _out = make_terminal()
        feed(term, "search type = note")
        self.assertEqual(app.calls[-1], ("search", "type = note"))
        feed(term, "search")
        self.assertEqual(term._prompt_label(), "criterion: ")
        feed(term, "type = task")
        self.assertEqual(app.calls[-1], ("search", "type = task"))


class CreateModifyWizardTests(unittest.TestCase):
    def test_create_prompts_for_type_then_fields(self):
        app, term, _out = make_terminal()
        feed(term, "create")
        self.assertIn("type", term._prompt_label())
        feed(term, "note", "Shopping: Milk")
        self.assertEqual(app.calls[-1], ("create", "note", {"text": "Shopping: Milk"}))

    def test_create_unknown_type_sets_status(self):
        app, term, _out = make_terminal()
        feed(term, "create series")
        self.assertEqual(app.status, "unknown PIR type: series")

    def test_create_task_skips_empty_optional_deadline(self):
        app, term, _out = make_terminal()
        feed(term, "create task", "Inbox", "")
        kind, type_name, fields = app.calls[-1]
        self.assertEqual((kind, type_name), ("create", "task"))
        self.assertEqual(fields, {"description": "Inbox"})

    def test_modify_without_selection_fails(self):
        app, term, _out = make_terminal()
        feed(term, "modify")
        self.assertEqual(app.status, "no PIR selected")

    def test_modify_empty_enter_omits_field(self):
        app, term, _out = make_terminal()
        app._selected = Note(1, "old")
        feed(term, "modify", "")
        self.assertEqual(app.calls[-1], ("modify", {}))

    def test_delete_yes_and_no(self):
        app, term, _out = make_terminal()
        app._selected = Note(1, "x")
        feed(term, "delete", "n")
        self.assertEqual(app.status, "delete cancelled")
        self.assertNotIn(("delete",), app.calls)
        feed(term, "delete", "y")
        self.assertIn(("delete",), app.calls)


class AlarmWizardTests(unittest.TestCase):
    def test_create_event_with_relative_and_absolute_alarms(self):
        app, term, _out = make_terminal()
        feed(
            term,
            "create event",
            "lecture",
            "2026-09-14T18:30:00+08:00",
            "y",
            "r",
            "1",
            "day",
            "y",
            "a",
            "2026-09-13T09:00:00+08:00",
            "n",
        )
        _kind, type_name, fields = app.calls[-1]
        self.assertEqual(type_name, "event")
        self.assertEqual(len(fields["alarms"]), 2)
        self.assertEqual(fields["alarms"][0].amount, 1)

    def test_invalid_alarm_kind_sets_status(self):
        app, term, _out = make_terminal()
        feed(
            term,
            "create event",
            "lecture",
            "2026-09-14T18:30:00+08:00",
            "y",
            "nope",
        )
        self.assertEqual(app.status, "enter relative or absolute")

    def test_alarm_kind_amount_and_unit_errors_retry(self):
        app, term, _out = make_terminal()
        feed(
            term,
            "create event",
            "lecture",
            "2026-09-14T18:30:00+08:00",
            "y",
            "nope",
            "relative",
            "x",
            "relative",
            "-1",
            "relative",
            "1",
            "fortnight",
            "relative",
            "0",
            "n",
        )
        fields = app.calls[-1][2]
        self.assertEqual(len(fields["alarms"]), 1)
        self.assertEqual(fields["alarms"][0].amount, 0)

    def test_replace_alarms_yes_no_and_invalid(self):
        app, term, _out = make_terminal()
        app._selected = Event(4, "lecture", "2026-09-14T18:30:00+08:00", [RelativeAlarm(0, "minute")])
        app.modified = app._selected
        feed(term, "modify", "", "", "maybe")
        self.assertEqual(app.status, "enter y or n")
        feed(term, "n")
        self.assertEqual(app.calls[-1][0], "modify")
        feed(term, "modify", "", "", "y", "n")
        self.assertIn("alarms", app.calls[-1][1])

    def test_modify_alarms_forgets_dismissed_for_that_id(self):
        app, term, _out = make_terminal()
        event = Event(4, "lecture", "2026-09-14T18:30:00+08:00")
        app._selected = event
        replacement = Event(4, "lecture", "2026-09-14T18:30:00+08:00", [RelativeAlarm(0, "minute")])
        app.modified = replacement
        term.dismissed = {(4, 0), (9, 0)}
        feed(term, "modify", "", "", "y", "n")
        self.assertEqual(term.dismissed, {(9, 0)})


class SaveLoadQuitTests(unittest.TestCase):
    def test_save_asks_path_when_untitled(self):
        app, term, _out = make_terminal()
        feed(term, "save")
        self.assertEqual(term._prompt_label(), "path: ")
        feed(term, "/tmp/demo")
        self.assertEqual(app.calls[-1], ("save", "/tmp/demo"))

    def test_save_as_empty_path_and_overwrite_cancel(self):
        app, term, _out = make_terminal()
        feed(term, "save as")
        feed(term, "")
        self.assertEqual(app.status, "path is required")
        app.overwrite = True
        feed(term, "save as /tmp/taken.pim", "n")
        self.assertEqual(app.status, "save as cancelled")
        feed(term, "save as /tmp/taken.pim", "y")
        self.assertEqual(app.calls[-1], ("save", "/tmp/taken.pim"))

    def test_load_empty_path_and_dirty_cancel(self):
        app, term, _out = make_terminal()
        feed(term, "load")
        feed(term, "")
        self.assertEqual(app.status, "path is required")
        app._dirty = True
        feed(term, "load /tmp/x.pim", "cancel")
        self.assertEqual(app.status, "load cancelled")

    def test_dirty_quit_save_discard_and_invalid_choice(self):
        app, term, _out = make_terminal()
        app._dirty = True
        term._running = True
        feed(term, "quit", "maybe")
        self.assertEqual(app.status, "enter save, discard, or cancel")
        feed(term, "cancel")
        self.assertEqual(app.status, "quit cancelled")
        self.assertTrue(term._running)
        feed(term, "quit", "discard")
        self.assertFalse(term._running)

    def test_dirty_quit_save_with_bound_file(self):
        app, term, _out = make_terminal()
        app._dirty = True
        app._bound = "/tmp/x.pim"
        term._running = True
        feed(term, "quit", "s")
        self.assertFalse(term._running)
        self.assertEqual(app.calls[-1], ("save", None))

    def test_eof_during_wizard_cancels_command(self):
        app, term, _out = make_terminal()
        term._running = True
        feed(term, "create")
        term._handle_eof()
        self.assertEqual(app.status, "command cancelled")
        self.assertFalse(term._running)
        self.assertEqual(term._prompts, [])

    def test_interrupt_on_clean_session_stops(self):
        app, term, _out = make_terminal()
        term._running = True
        term._handle_interrupt()
        self.assertFalse(term._running)

    def test_eof_on_dirty_non_tty_stops(self):
        app, term, _out = make_terminal()
        app._dirty = True
        term._running = True
        feed(term, "quit")
        term._handle_eof()
        self.assertFalse(term._running)
        self.assertIn("unsaved changes", app.status)

    def test_load_failed_does_not_clear_dismissed(self):
        app, term, _out = make_terminal()
        term.dismissed.add((1, 0))
        app.load_ok = False
        feed(term, "load /tmp/x.pim")
        self.assertEqual(term.dismissed, {(1, 0)})
        app.load_ok = True
        feed(term, "load /tmp/x.pim")
        self.assertEqual(term.dismissed, set())


class LayoutAndPaintTests(unittest.TestCase):
    def test_layout_empty_untitled_and_menu(self):
        _app, term, _out = make_terminal()
        lines = term._layout()
        self.assertTrue(lines[0].startswith("PIM  untitled"))
        self.assertIn("ALARMS", lines)
        self.assertIn("  (none)", lines)
        self.assertIn("    (empty)", lines)
        self.assertIn("  (no selection)", lines)
        self.assertIn(MENU, lines)

    def test_layout_truncates_long_name_and_marks_selection(self):
        app, term, _out = make_terminal()
        note = Note(1, "abcdefghijklmnopqrstuvwxyz extra")
        app._result = [note]
        app._selected = note
        app._dirty = True
        app._bound = "/tmp/demo.pim"
        app.print_text = "printed"
        app._due = [FakeDue()]
        lines = term._layout()
        joined = "\n".join(lines)
        self.assertIn("PIM  /tmp/demo.pim*", joined)
        self.assertIn("OVERDUE", joined)
        self.assertIn("(dismiss)", joined)
        self.assertIn("abc", joined)
        self.assertIn("...", joined)
        self.assertIn(">   1    1  note", joined)
        self.assertIn("PRINT", joined)

    def test_dismiss_first_due_alarm(self):
        app, term, _out = make_terminal()
        app._due = [FakeDue()]
        feed(term, "dismiss")
        self.assertEqual(term.dismissed, {(4, 0)})
        self.assertIn("Dismissed alarm on Id 4", app.status)
        feed(term, "dismiss")
        self.assertEqual(app.status, "no alarm to dismiss")

    def test_paint_skips_unchanged_snapshot(self):
        _app, term, out = make_terminal()
        term.render()
        before = out.getvalue()
        self.assertTrue(term._paint(force=False))
        after_first = out.getvalue()
        self.assertGreater(len(after_first), len(before))
        self.assertFalse(term._paint(force=False))
        self.assertEqual(out.getvalue(), after_first)

    def test_tty_render_writes_ansi_clear(self):
        _app, term, out = make_terminal(tty=True)
        term.render()
        self.assertIn("\033[2J\033[H", out.getvalue())

    def test_now_datetime_callable_and_wall_clock(self):
        instant = parse_datetime("2026-09-14T18:30:00+08:00")
        _app, term, _out = make_terminal(now=instant)
        self.assertEqual(term._now_dt(), instant)
        _app, term2, _out = make_terminal(now=lambda: instant)
        self.assertEqual(term2._now_dt(), instant)
        _app, term3, _out = make_terminal()
        self.assertIsInstance(term3._now_dt(), datetime)
        self.assertEqual(term3._now_dt().tzinfo, HKT)

    def test_interrupt_during_dirty_prompt_asks_again(self):
        app, term, _out = make_terminal()
        app._dirty = True
        feed(term, "quit")
        term._handle_interrupt()
        self.assertEqual(app.status, "enter save, discard, or cancel")


class AcceleratorAndCursesGateTests(unittest.TestCase):
    def test_arrows_move_selection_in_current_result(self):
        app, term, _out = make_terminal()
        app._result = [Note(1, "a"), Note(2, "b"), Note(3, "c")]
        term.apply_accelerator("select_down")
        self.assertEqual(app.calls[-1], ("row", "1"))
        self.assertEqual(app.selected_id(), 1)
        term.apply_accelerator("select_down")
        self.assertEqual(app.selected_id(), 2)
        term.apply_accelerator("select_up")
        self.assertEqual(app.selected_id(), 1)
        term.apply_accelerator("select_last")
        self.assertEqual(app.selected_id(), 3)
        term.apply_accelerator("select_first")
        self.assertEqual(app.selected_id(), 1)

    def test_empty_result_move_sets_status(self):
        app, term, _out = make_terminal()
        term.apply_accelerator("select_down")
        self.assertEqual(app.status, "Current Result is empty")

    def test_save_accelerator_asks_path_when_untitled(self):
        app, term, _out = make_terminal()
        term.apply_accelerator("save")
        self.assertEqual(term._prompt_label(), "path: ")
        self.assertNotIn(("save", None), app.calls)

    def test_create_and_search_accelerators_open_prompts(self):
        app, term, _out = make_terminal()
        term.apply_accelerator("create")
        self.assertIn("type", term._prompt_label())
        term.cancel_prompt()
        self.assertEqual(app.status, "command cancelled")
        self.assertEqual(term._prompts, [])
        term.apply_accelerator("search")
        self.assertEqual(term._prompt_label(), "criterion: ")

    def test_slash_verbs_still_work_after_cancel(self):
        app, term, _out = make_terminal()
        term.apply_accelerator("search")
        feed(term, "type = note")
        self.assertEqual(app.calls[-1], ("search", "type = note"))

    def test_use_curses_false_when_not_a_tty(self):
        _app, term, _out = make_terminal()
        self.assertFalse(term._use_curses())

    def test_use_curses_false_when_env_disables_it(self):
        import os

        class Tty:
            def isatty(self):
                return True

        app = FakeApp()
        term = Terminal(app, stdin=Tty(), stdout=Tty())
        previous = os.environ.get("PIM_NO_CURSES")
        os.environ["PIM_NO_CURSES"] = "1"
        try:
            self.assertFalse(term._use_curses())
        finally:
            if previous is None:
                os.environ.pop("PIM_NO_CURSES", None)
            else:
                os.environ["PIM_NO_CURSES"] = previous

    def test_esc_on_dirty_prompt_does_not_drop_changes(self):
        app, term, _out = make_terminal()
        app._dirty = True
        term._running = True
        feed(term, "quit")
        term.cancel_prompt()
        self.assertEqual(app.status, "enter save, discard, or cancel")
        self.assertTrue(term._prompts)
        self.assertTrue(term._running)
