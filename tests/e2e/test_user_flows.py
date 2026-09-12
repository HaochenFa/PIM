"""US1–US11 through scripted create/search/modify/print/delete/save/load."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from model import PIM, parse_datetime
from tests.e2e.harness import result_ids, run_script


def fixture_lines():
    """Keystrokes that create the ACCEPTANCE §4 fixture."""
    return [
        "create note",
        "Shopping: Milk",
        "create task",
        "Submit PIM",
        "2026-11-20T20:00:00+08:00",
        "create task",
        "Inbox",
        "",
        "create event",
        "COMP3211 lecture",
        "2026-09-14T18:30:00+08:00",
        "y",
        "relative",
        "1",
        "day",
        "y",
        "relative",
        "0",
        "y",
        "absolute",
        "2026-09-13T09:00:00+08:00",
        "n",
        "create contact",
        "Ada",
        "",
        "12345678",
        "create contact",
        "Ada",
        "HK",
        "",
    ]


class CreateModifySearchPrintDeleteTests(unittest.TestCase):
    def test_create_four_types_and_empty_required_field_fails(self):
        app, _term, out = run_script(
            [
                "create note",
                "   ",
                "create note",
                "Shopping: Milk",
                "create task",
                "Inbox",
                "",
                "create event",
                "lecture",
                "2026-09-14T18:30:00+08:00",
                "n",
                "create contact",
                "Ada",
                "",
                "",
                "quit",
                "discard",
            ]
        )
        self.assertIn("text is required", out)
        self.assertEqual(len(app.pim.all()), 4)
        self.assertEqual(app.pim.get(1).type_name, "note")
        self.assertEqual(app.pim.get(2).type_name, "task")
        self.assertEqual(app.pim.get(3).type_name, "event")
        self.assertEqual(app.pim.get(4).type_name, "contact")

    def test_modify_empty_enter_keeps_values_and_no_selection_fails(self):
        app, _term, out = run_script(
            [
                "modify",
                *fixture_lines(),
                "id 1",
                "modify",
                "",
                "quit",
                "discard",
            ]
        )
        self.assertIn("no PIR selected", out)
        self.assertEqual(app.pim.get(1).text, "Shopping: Milk")
        self.assertIn("No changes", out)

    def test_search_fixture_criteria_and_syntax_error_leaves_list(self):
        app, _term, out = run_script(
            [
                *fixture_lines(),
                "search type = contact && name contains \"ada\"",
                "search deadline < 2026-11-21T00:00:00+08:00",
                "search type =",
                "quit",
                "discard",
            ]
        )
        self.assertEqual(result_ids(app), [2])
        self.assertIn("search syntax error", out)
        self.assertNotIn(3, result_ids(app))

    def test_print_requires_selection_print_all_is_current_result(self):
        app, _term, out = run_script(
            [
                *fixture_lines(),
                "search type = note",
                "print",
                "print all",
                "1",
                "print",
                "quit",
                "discard",
            ]
        )
        self.assertEqual(result_ids(app), [1])
        self.assertIn("Printed 1 PIR(s) in Current Result", out)
        self.assertIn("Printed Id 1", out)

    def test_delete_no_keeps_yes_removes_and_id_is_not_reused(self):
        app, _term, out = run_script(
            [
                *fixture_lines(),
                "id 2",
                "delete",
                "n",
                "delete",
                "y",
                "create note",
                "after delete",
                "quit",
                "discard",
            ]
        )
        self.assertIn("delete cancelled", out)
        self.assertTrue(all(pir.id != 2 for pir in app.pim.all()))
        created = [pir for pir in app.pim.all() if pir.type_name == "note" and pir.text == "after delete"][0]
        self.assertGreaterEqual(created.id, 7)
        self.assertNotEqual(created.id, 2)

    def test_unknown_command_does_not_mutate(self):
        app, _term, out = run_script(
            [
                *fixture_lines(),
                "explode",
                "quit",
                "discard",
            ]
        )
        self.assertIn("unknown command: explode", out)
        self.assertEqual(len(app.pim.all()), 6)


class StoreLoadDirtyTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_as_appends_pim_and_load_rejects_other_extension(self):
        dest = self.dir / "demo"
        other = self.dir / "demo.json"
        other.write_text("{}", encoding="utf-8")
        app, _term, out = run_script(
            [
                *fixture_lines(),
                f"save as {dest}",
                f"load {other}",
                "quit",
            ]
        )
        self.assertTrue((self.dir / "demo.pim").is_file())
        self.assertFalse(app.is_dirty())
        self.assertIn("path must have a .pim extension", out)
        self.assertEqual(len(app.pim.all()), 6)

    def test_dirty_quit_cancel_then_discard(self):
        app, _term, out = run_script(
            [
                "create note",
                "keep me",
                "quit",
                "cancel",
                "quit",
                "discard",
            ]
        )
        self.assertIn("quit cancelled", out)
        self.assertEqual(len(app.pim.all()), 1)
        self.assertEqual(app.pim.get(1).text, "keep me")

    def test_dirty_load_cancel_leaves_working_collection(self):
        saved = self.dir / "ok.pim"
        seed = PIM()
        seed.create_note("from file")
        seed.save(saved)
        app, _term, out = run_script(
            [
                "create note",
                "unsaved",
                f"load {saved}",
                "cancel",
                "quit",
                "discard",
            ]
        )
        self.assertIn("load cancelled", out)
        self.assertEqual(app.pim.get(1).text, "unsaved")

    def test_dirty_load_discard_replaces_collection(self):
        saved = self.dir / "ok.pim"
        seed = PIM()
        seed.create_note("from file")
        seed.save(saved)
        app, _term, out = run_script(
            [
                "create note",
                "unsaved",
                f"load {saved}",
                "discard",
                "quit",
            ]
        )
        self.assertEqual(app.pim.get(1).text, "from file")
        self.assertIn("Loaded", out)

    def test_save_as_overwrite_confirm_yes(self):
        existing = self.dir / "taken.pim"
        existing.write_text('{"format":"pim/v1","next_id":1,"pirs":[]}\n', encoding="utf-8")
        app, _term, out = run_script(
            [
                "create note",
                "overwrite me",
                f"save as {existing}",
                "y",
                "quit",
            ]
        )
        self.assertFalse(app.is_dirty())
        self.assertIn("Saved", out)
        loaded = PIM()
        loaded.load(existing)
        self.assertEqual(loaded.get(1).text, "overwrite me")


class ModifyEventStartTests(unittest.TestCase):
    def test_changing_start_moves_relative_not_absolute(self):
        app, _term, _out = run_script(
            [
                *fixture_lines(),
                "id 4",
                "modify",
                "",
                "2026-09-21T18:30:00+08:00",
                "n",
                "quit",
                "discard",
            ]
        )
        event = app.pim.get(4)
        times = event.effective_alarm_times()
        self.assertEqual(times[0], parse_datetime("2026-09-20T18:30:00+08:00"))
        self.assertEqual(times[1], parse_datetime("2026-09-21T18:30:00+08:00"))
        self.assertEqual(times[2], parse_datetime("2026-09-13T09:00:00+08:00"))


if __name__ == "__main__":
    unittest.main()
