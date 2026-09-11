"""curses UI helpers that do not need a real TTY."""

import unittest

from view.curses_ui import CursesUI
from view.keys import CREATE, SEARCH
from tests.unit.test_terminal import make_terminal


class CursesHelperTests(unittest.TestCase):
    def test_character_actions_without_a_screen(self):
        _app, term, _out = make_terminal()
        ui = CursesUI(term, object())
        self.assertEqual(ui._action("c"), CREATE)
        self.assertEqual(ui._action("/"), SEARCH)
        self.assertIsNone(ui._action("s"))

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
