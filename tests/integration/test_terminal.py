"""view.Terminal wired to controller.App and model.PIM, no event-loop thread."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from controller.app import App, HELP
from model import PIM, parse_datetime
from tests.fixture import make_fixture
from view.terminal import Terminal


def feed(term: Terminal, *lines: str) -> None:
    """Deliver prompt answers and commands on the same thread as the model."""
    for line in lines:
        term._handle_line(line)


def session(pim=None, now=None):
    """App + Terminal writing to a buffer."""
    app = App(pim if pim is not None else PIM())
    out = io.StringIO()
    term = Terminal(app, stdin=io.StringIO(), stdout=out, now=now)
    return app, term, out


class TerminalAppCreateSearchTests(unittest.TestCase):
    def test_create_note_wizard_updates_current_result(self):
        app, term, _out = session()
        feed(term, "create note", "Shopping: Milk")
        self.assertEqual(app.selected_id(), 1)
        self.assertEqual(app.pim.get(1).text, "Shopping: Milk")
        self.assertIn("Created Note Id 1", app.status)

    def test_search_then_print_all_is_hits_only(self):
        app, term, _out = session(make_fixture())
        feed(term, "search type = note", "print all")
        self.assertIn("Shopping: Milk", app.print_text)
        self.assertNotIn("Submit PIM", app.print_text)
        feed(term, "clear")
        self.assertEqual(len(app.current_result()), 6)

    def test_help_status_is_controller_help(self):
        app, term, _out = session()
        feed(term, "help")
        self.assertEqual(app.status, HELP)


class TerminalAppModifyDeleteTests(unittest.TestCase):
    def test_modify_keeps_id_and_empty_enter_keeps_text(self):
        app, term, _out = session(make_fixture())
        feed(term, "id 1", "modify", "")
        self.assertEqual(app.pim.get(1).text, "Shopping: Milk")
        self.assertEqual(app.status, "No changes")
        feed(term, "modify", "Shopping: Bread")
        self.assertEqual(app.pim.get(1).id, 1)
        self.assertEqual(app.pim.get(1).text, "Shopping: Bread")

    def test_delete_confirm_yes_does_not_reuse_id(self):
        app, term, _out = session(make_fixture())
        feed(term, "id 2", "delete", "y")
        self.assertTrue(all(pir.id != 2 for pir in app.pim.all()))
        feed(term, "create note", "after")
        self.assertGreaterEqual(app.selected_id(), 7)


class TerminalAppPersistAlertTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_as_and_load_round_trip(self):
        app, term, _out = session(make_fixture())
        dest = self.dir / "demo"
        feed(term, f"save as {dest}")
        self.assertFalse(app.is_dirty())
        other, term2, _ = session()
        feed(term2, f"load {self.dir / 'demo.pim'}")
        self.assertEqual([pir.id for pir in other.current_result()], [1, 2, 3, 4, 5, 6])

    def test_dismiss_is_view_memory_not_pim_state(self):
        now = parse_datetime("2026-09-13T09:00:00+08:00")
        app, term, _out = session(make_fixture(), now=now)
        self.assertTrue(term.visible_due())
        feed(term, "dismiss")
        self.assertEqual(term.visible_due(), [])
        self.assertTrue(app.due_alarms(now))

    def test_layout_shows_search_and_dirty_flag(self):
        app, term, _out = session(make_fixture())
        feed(term, "id 1", "modify", "changed")
        lines = "\n".join(term._layout())
        self.assertIn("untitled*", lines)
        feed(term, "search type = note")
        lines = "\n".join(term._layout())
        self.assertIn("Current Result (search)", lines)
        self.assertIn("changed", lines)
        self.assertNotIn("Submit PIM", lines)


if __name__ == "__main__":
    unittest.main()
