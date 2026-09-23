"""curses UI helpers that do not need a real TTY."""

import unittest

from view.curses_ui import CursesUI
from view.keys import CREATE, SEARCH
from tests.unit.test_terminal import make_terminal
from model import Note


class CursesHelperTests(unittest.TestCase):
    def test_character_actions_without_a_screen(self):
        _app, term, _out = make_terminal()
        ui = CursesUI(term, object())
        self.assertEqual(ui._action("c"), CREATE)
        self.assertEqual(ui._action("/"), SEARCH)
        self.assertIsNone(ui._action("s"))

    def test_type_selector_letter_submits_note(self):
        app, term, _out = make_terminal()
        ui = CursesUI(term, object())
        term.apply_accelerator("create")
        ui._sync_chooser()
        self.assertTrue(ui._handle_chooser_key("n"))
        self.assertEqual(app.calls, [])
        self.assertIn("text", term._prompt_label())
        self.assertIsNone(term.current_chooser())

    def test_type_selector_arrows_then_enter(self):
        app, term, _out = make_terminal()
        app._result = []
        ui = CursesUI(term, object())
        term.apply_accelerator("create")
        ui._sync_chooser()
        ui._handle_chooser_key("l")
        ui._handle_chooser_key("l")
        chooser = term.current_chooser()
        self.assertEqual(chooser.value_at(ui.choice_index), "event")
        ui._handle_chooser_key("\n")
        self.assertIn("description", term._prompt_label())

    def test_delete_selector_enter_on_default_cancels(self):
        app, term, _out = make_terminal()
        app._selected = Note(1, "x")
        ui = CursesUI(term, object())
        term.apply_accelerator("delete")
        ui._sync_chooser()
        ui._handle_chooser_key("\n")
        self.assertEqual(app.status, "delete cancelled")
        self.assertNotIn(("delete",), app.calls)

    def test_escape_clears_typed_command_not_running_flag(self):
        app, term, _out = make_terminal()
        term._running = True
        ui = CursesUI(term, object())
        ui.buffer = "create"
        ui.cursor = 6
        ui.raw_command = True
        ui._escape()
        self.assertEqual(ui.buffer, "")
        self.assertFalse(ui.raw_command)
        self.assertEqual(app.status, "command cancelled")
        self.assertTrue(term._running)

    def test_search_syntax_error_keeps_the_typed_line(self):
        app, term, _out = make_terminal()

        def bad_search(line):
            app.calls.append(("search", line))
            app.set_status("search syntax error: type =", "err")
            return False

        app.search = bad_search
        term.ask("criterion: ", lambda value: app.search(value))
        ui = CursesUI(term, object())
        ui.buffer = "type ="
        ui.cursor = 6
        ui._submit()
        self.assertEqual(ui.buffer, "type =")
        self.assertIn("criterion", term._prompt_label())
        self.assertEqual(app.status_kind, "err")

    def test_idle_escape_clears_an_active_search(self):
        app, term, _out = make_terminal()
        app._criterion = True
        app._criterion_line = "type = note"
        ui = CursesUI(term, object())
        ui._escape()
        self.assertIn(("clear",), app.calls)
        self.assertFalse(app.has_criterion())

    def test_idle_escape_without_search_does_not_quit(self):
        app, term, _out = make_terminal()
        term._running = True
        ui = CursesUI(term, object())
        ui._escape()
        self.assertTrue(term._running)
        self.assertNotIn(("clear",), app.calls)

    def test_safe_turns_unexpected_error_into_status(self):
        """CursesUI._safe reports a RuntimeError as `command failed` instead of raising."""
        app, term, _out = make_terminal()
        ui = CursesUI(term, object())

        def boom():
            raise RuntimeError("boom")

        ui._safe(boom)
        self.assertEqual(app.status, "command failed")
        self.assertEqual(app.status_kind, "err")
