"""E2E: remaining command vocabulary, aliases, and wizard prompts through run()."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from controller.app import HELP, App
from model import PIM
from tests.e2e.harness import result_ids, run_script
from tests.e2e.test_user_flows import fixture_lines


class CommandVocabularyTests(unittest.TestCase):
    def test_help_clear_and_q_alias(self):
        app, term, out = run_script(
            [
                *fixture_lines(),
                "help",
                "search type = note",
                "clear",
                "q",
                "discard",
            ]
        )
        self.assertIn(HELP, out)
        self.assertEqual(len(result_ids(app)), 6)
        self.assertIn("Search cleared", out)
        self.assertNotIn("unknown command: q", out)
        self.assertFalse(term._running)

    def test_create_type_prompt_and_search_criterion_prompt(self):
        app, _term, out = run_script(
            [
                "create",
                "note",
                "hello",
                "search",
                "type = note",
                "quit",
                "discard",
            ]
        )
        self.assertEqual(result_ids(app), [1])
        self.assertIn("1 match(es)", out)

    def test_exit_alias_on_clean_collection(self):
        _app, term, out = run_script(["exit"])
        self.assertNotIn("unknown command: exit", out)
        self.assertFalse(term._running)

    def test_missing_quit_times_out(self):
        with self.assertRaises(TimeoutError):
            run_script(["help"], timeout=1.5)


class SaveLoadPromptTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_untitled_asks_path(self):
        dest = self.dir / "via-save"
        app, _term, out = run_script(
            [
                "create note",
                "body",
                "save",
                str(dest),
                "quit",
            ]
        )
        self.assertTrue((self.dir / "via-save.pim").is_file())
        self.assertFalse(app.is_dirty())
        self.assertIn("Saved", out)

    def test_save_as_and_load_prompt_for_path(self):
        dest = self.dir / "named.pim"
        seed = PIM()
        seed.create_note("from disk")
        seed.save(dest)
        app, _term, out = run_script(
            [
                "load",
                str(dest),
                "quit",
            ]
        )
        self.assertEqual(app.pim.get(1).text, "from disk")
        self.assertIn("Loaded", out)

    def test_overwrite_no_leaves_existing_file(self):
        existing = self.dir / "taken.pim"
        existing.write_text('{"format":"pim/v1","next_id":1,"pirs":[]}\n', encoding="utf-8")
        _app, _term, out = run_script(
            [
                "create note",
                "new",
                f"save as {existing}",
                "n",
                "quit",
                "discard",
            ]
        )
        self.assertIn("save as cancelled", out)
        loaded = PIM()
        loaded.load(existing)
        self.assertEqual(loaded.all(), [])

    def test_dirty_quit_save_without_bound_file_asks_path(self):
        dest = self.dir / "from-quit.pim"
        app, _term, out = run_script(
            [
                "create note",
                "keep",
                "quit",
                "save",
                str(dest),
            ]
        )
        self.assertTrue(dest.is_file())
        self.assertFalse(app.is_dirty())
        self.assertIn("Saved", out)


class WizardErrorTests(unittest.TestCase):
    def test_invalid_alarm_kind_then_valid_relative_zero(self):
        app, _term, out = run_script(
            [
                "create event",
                "lecture",
                "2026-09-14T18:30:00+08:00",
                "y",
                "nope",
                "relative",
                "0",
                "n",
                "quit",
                "discard",
            ]
        )
        self.assertIn("enter relative or absolute", out)
        self.assertEqual(len(app.pim.get(1).alarms), 1)

    def test_overflowing_relative_alarm_fails_create_and_session_continues(self):
        """A1 repro: 999999999 weeks before start is a status-line error, not a crash."""
        app, term, out = run_script(
            [
                "create event",
                "overflow",
                "2026-09-14T18:30:00+08:00",
                "y",
                "relative",
                "999999999",
                "week",
                "n",
                "create note",
                "still alive",
                "quit",
                "discard",
            ]
        )
        self.assertIn("alarm time is out of range", out)
        self.assertEqual([pir.type_name for pir in app.pim.all()], ["note"])
        self.assertFalse(term._running)

    def test_replace_alarms_yes_replaces_list(self):
        app, _term, _out = run_script(
            [
                "create event",
                "lecture",
                "2026-09-14T18:30:00+08:00",
                "y",
                "relative",
                "1",
                "hour",
                "n",
                "1",
                "modify",
                "",
                "",
                "y",
                "y",
                "relative",
                "0",
                "n",
                "quit",
                "discard",
            ]
        )
        alarms = app.pim.get(1).alarms
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].amount, 0)

    def test_yes_alias_for_delete(self):
        app, _term, _out = run_script(
            [
                "create note",
                "gone",
                "delete",
                "yes",
                "quit",
                "discard",
            ]
        )
        self.assertEqual(app.pim.all(), [])


class EventLoopErrorTests(unittest.TestCase):
    def test_oserror_during_save_becomes_status_not_crash(self):
        class BoomSave(App):
            def save(self, path=None):
                raise OSError("disk full")

        _app, _term, out = run_script(
            [
                "create note",
                "x",
                "save",
                "/tmp/pim-boom",
                "quit",
                "discard",
            ],
            app=BoomSave(PIM()),
        )
        self.assertIn("disk full", out)

    def test_unexpected_command_error_is_status_not_crash(self):
        """A RuntimeError inside a command shows `command failed`; the session continues."""

        class BoomSearch(App):
            def search(self, line):
                raise RuntimeError("boom")

        _app, term, out = run_script(
            ["search type = note", "help", "quit"],
            app=BoomSearch(PIM()),
        )
        self.assertIn("command failed", out)
        self.assertIn(HELP, out)
        self.assertFalse(term._running)

    def test_run_script_reraises_event_loop_crash(self):
        """The harness surfaces a crash outside command handling (here: painting alarms)."""

        class BoomDue(App):
            def due_alarms(self, now):
                raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            run_script(["quit"], app=BoomDue(PIM()))


if __name__ == "__main__":
    unittest.main()
